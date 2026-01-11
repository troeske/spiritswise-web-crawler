"""
Unit tests for ProductPipeline V2 migration.

These tests verify that UnifiedProductPipeline uses V2 components:
- AIExtractorV2 instead of AIExtractor
- AIClientV2 instead of AIEnhancementClient

TDD approach: Tests written BEFORE migration.
"""

import uuid
from decimal import Decimal
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crawler.services.product_pipeline import UnifiedProductPipeline, PipelineResult


class TestProductPipelineUsesV2Extractor:
    """Verify ProductPipeline uses AIExtractorV2."""

    def test_imports_ai_extractor_v2(self):
        """Verify the module imports AIExtractorV2, not AIExtractor."""
        import inspect
        import crawler.services.product_pipeline as pipeline_module

        # Get the source code of the module
        source = inspect.getsource(pipeline_module)

        # Check that get_ai_extractor_v2 is imported/used
        assert 'ai_extractor_v2' in source, \
            "Should reference ai_extractor_v2 module"

        # Should NOT have V1 import
        assert 'from crawler.discovery.extractors.ai_extractor import AIExtractor' not in source, \
            "Should NOT import AIExtractor from ai_extractor (V1)"

    def test_default_extractor_is_v2_type(self):
        """Verify default AI extractor is AIExtractorV2 type."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        # Patch at the point where the module imports the function
        with patch(
            'crawler.discovery.extractors.ai_extractor_v2.get_ai_extractor_v2'
        ) as mock_get:
            mock_extractor = MagicMock(spec=AIExtractorV2)
            mock_get.return_value = mock_extractor

            # Need to also patch smart_crawler dependencies
            with patch('crawler.services.scrapingbee_client.ScrapingBeeClient'):
                with patch('crawler.services.ai_client_v2.get_ai_client_v2'):
                    with patch('crawler.services.smart_crawler.SmartCrawler'):
                        pipeline = UnifiedProductPipeline()

                        # Verify get_ai_extractor_v2 was called
                        mock_get.assert_called_once()
                        assert pipeline.ai_extractor == mock_extractor

    @pytest.mark.asyncio
    async def test_extractor_extract_called_with_url_and_context(self):
        """Verify extractor.extract() is called with correct arguments."""
        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "palate_description": "Smooth and complex",
            "palate_flavors": ["vanilla", "oak", "caramel"],
        }

        # Mock brand resolution
        with patch.object(
            UnifiedProductPipeline, '_resolve_brand', new_callable=AsyncMock
        ) as mock_brand:
            mock_brand.return_value = None

            # Mock save product
            with patch.object(
                UnifiedProductPipeline, '_save_product', new_callable=AsyncMock
            ) as mock_save:
                mock_product = MagicMock()
                mock_product.id = uuid.uuid4()
                mock_save.return_value = mock_product

                # Provide both ai_extractor and smart_crawler to avoid initialization issues
                pipeline = UnifiedProductPipeline(
                    ai_extractor=mock_extractor,
                    smart_crawler=MagicMock()
                )

                url = "https://example.com/product/123"
                context = {"source": "iwsc", "year": 2024}

                result = await pipeline.process_url(url, context)

                # Verify extract was called with URL and context
                mock_extractor.extract.assert_called_once_with(url, context)
                assert result.success


class TestProductPipelineUsesV2Client:
    """Verify ProductPipeline uses AIClientV2."""

    def test_smart_crawler_uses_v2_client(self):
        """Verify SmartCrawler is initialized with AIClientV2."""
        from crawler.services.ai_client_v2 import AIClientV2

        # Patch at the actual import location in the module
        with patch(
            'crawler.services.ai_client_v2.get_ai_client_v2'
        ) as mock_get_client:
            mock_client = MagicMock(spec=AIClientV2)
            mock_get_client.return_value = mock_client

            with patch(
                'crawler.discovery.extractors.ai_extractor_v2.get_ai_extractor_v2'
            ) as mock_get_ext:
                mock_extractor = MagicMock()
                mock_get_ext.return_value = mock_extractor

                with patch('crawler.services.scrapingbee_client.ScrapingBeeClient'):
                    with patch('crawler.services.smart_crawler.SmartCrawler') as mock_smart_crawler:
                        # Create pipeline - should use V2 client for SmartCrawler
                        pipeline = UnifiedProductPipeline()

                        # Verify V2 client getter was called
                        mock_get_client.assert_called_once()

    def test_ai_client_v2_imported_not_v1(self):
        """Verify ai_client_v2 is imported, not ai_client."""
        import inspect
        import crawler.services.product_pipeline as pipeline_module

        # Get the source code of the module
        source = inspect.getsource(pipeline_module)

        # Check that get_ai_client_v2 is used
        assert 'ai_client_v2' in source, \
            "Should reference ai_client_v2 module"

        # Should NOT have V1 import
        assert 'from crawler.services.ai_client import AIEnhancementClient' not in source, \
            "Should NOT import AIEnhancementClient from ai_client (V1)"


class TestProductPipelineExtractsTastingNotes:
    """Verify extraction includes tasting note fields."""

    @pytest.mark.asyncio
    async def test_palate_fields_extracted(self):
        """Verify palate tasting fields are extracted."""
        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = {
            "name": "Highland Park 18",
            "brand": "Highland Park",
            "palate_description": "Rich and full-bodied with honey and smoke",
            "palate_flavors": ["honey", "smoke", "heather", "sherry"],
            "initial_taste": "Sweet honey notes",
            "mid_palate_evolution": "Smoke develops gradually",
            "mouthfeel": "Creamy and oily",
        }

        with patch.object(
            UnifiedProductPipeline, '_resolve_brand', new_callable=AsyncMock
        ) as mock_brand:
            mock_brand.return_value = None

            with patch.object(
                UnifiedProductPipeline, '_save_product', new_callable=AsyncMock
            ) as mock_save:
                mock_product = MagicMock()
                mock_product.id = uuid.uuid4()
                mock_save.return_value = mock_product

                pipeline = UnifiedProductPipeline(
                    ai_extractor=mock_extractor,
                    smart_crawler=MagicMock()
                )
                result = await pipeline.process_url(
                    "https://example.com/product",
                    {"source": "test"}
                )

                assert result.success
                # Verify tasting profile fields in extracted data
                assert "palate_description" in result.extracted_data
                assert "palate_flavors" in result.extracted_data
                assert len(result.extracted_data["palate_flavors"]) >= 2

    @pytest.mark.asyncio
    async def test_nose_fields_extracted(self):
        """Verify nose/aroma tasting fields are extracted."""
        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = {
            "name": "Macallan 12",
            "brand": "Macallan",
            "nose_description": "Rich sherry with dried fruits",
            "primary_aromas": ["sherry", "dried fruits", "vanilla"],
            "secondary_aromas": ["oak", "spice"],
        }

        with patch.object(
            UnifiedProductPipeline, '_resolve_brand', new_callable=AsyncMock
        ) as mock_brand:
            mock_brand.return_value = None

            with patch.object(
                UnifiedProductPipeline, '_save_product', new_callable=AsyncMock
            ) as mock_save:
                mock_product = MagicMock()
                mock_product.id = uuid.uuid4()
                mock_save.return_value = mock_product

                pipeline = UnifiedProductPipeline(
                    ai_extractor=mock_extractor,
                    smart_crawler=MagicMock()
                )
                result = await pipeline.process_url(
                    "https://example.com/product",
                    {"source": "test"}
                )

                assert result.success
                assert "nose_description" in result.extracted_data
                assert "primary_aromas" in result.extracted_data

    @pytest.mark.asyncio
    async def test_finish_fields_extracted(self):
        """Verify finish tasting fields are extracted."""
        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = {
            "name": "Lagavulin 16",
            "brand": "Lagavulin",
            "finish_description": "Long, smoky, with maritime notes",
            "finish_flavors": ["smoke", "peat", "iodine"],
            "finish_length": 45,
        }

        with patch.object(
            UnifiedProductPipeline, '_resolve_brand', new_callable=AsyncMock
        ) as mock_brand:
            mock_brand.return_value = None

            with patch.object(
                UnifiedProductPipeline, '_save_product', new_callable=AsyncMock
            ) as mock_save:
                mock_product = MagicMock()
                mock_product.id = uuid.uuid4()
                mock_save.return_value = mock_product

                pipeline = UnifiedProductPipeline(
                    ai_extractor=mock_extractor,
                    smart_crawler=MagicMock()
                )
                result = await pipeline.process_url(
                    "https://example.com/product",
                    {"source": "test"}
                )

                assert result.success
                assert "finish_description" in result.extracted_data
                assert "finish_flavors" in result.extracted_data


class TestProductPipelineCompletenessWithV2:
    """Test completeness scoring works correctly with V2 extracted data."""

    def test_completeness_scoring_with_full_tasting_profile(self):
        """Verify completeness scoring for full tasting profile."""
        pipeline = UnifiedProductPipeline(
            ai_extractor=MagicMock(),
            smart_crawler=MagicMock()
        )

        extracted_data = {
            "name": "Complete Whiskey",
            "brand": "Test Brand",
            "product_type": "whiskey",
            "abv": 46.0,
            "description": "A complete whiskey",
            # Full tasting profile (40 points)
            "palate_flavors": ["vanilla", "oak", "caramel"],
            "palate_description": "Smooth and rich",
            "initial_taste": "Sweet entry",
            "mid_palate_evolution": "Develops complexity",
            "mouthfeel": "Creamy",
            "nose_description": "Aromatic",
            "primary_aromas": ["honey", "flowers"],
            "finish_description": "Long finish",
            "finish_flavors": ["spice", "oak"],
            "finish_length": 30,
            # Enrichment
            "best_price": 75.00,
            "images": ["image1.jpg"],
        }

        score = pipeline._calculate_completeness(extracted_data)

        # Should be high score due to tasting profile
        # ID (15) + Basic (15) + Tasting (40) + Enrichment (10) = 80+
        assert score >= 75, f"Expected score >= 75, got {score}"

    def test_status_requires_palate_for_complete(self):
        """Verify COMPLETE status requires palate data."""
        pipeline = UnifiedProductPipeline(
            ai_extractor=MagicMock(),
            smart_crawler=MagicMock()
        )

        # High score but NO palate data
        extracted_data = {
            "name": "Test Product",
            "brand": "Test Brand",
            "abv": 40.0,
            "description": "A test whiskey",
            "nose_description": "Nice nose",
            "finish_description": "Long finish",
            "best_price": 50.00,
            "images": ["img.jpg"],
            "ratings": [{"source": "test", "score": 90}],
        }

        completeness_score = pipeline._calculate_completeness(extracted_data)
        status = pipeline._determine_status(extracted_data, completeness_score)

        # Without palate data, status should be partial, not complete
        assert status in ["partial", "incomplete"], \
            f"Expected partial/incomplete without palate, got {status}"

    def test_status_complete_with_palate_data(self):
        """Verify COMPLETE status achieved with palate data."""
        pipeline = UnifiedProductPipeline(
            ai_extractor=MagicMock(),
            smart_crawler=MagicMock()
        )

        extracted_data = {
            "name": "Test Product",
            "brand": "Test Brand",
            "product_type": "whiskey",
            "abv": 40.0,
            "description": "A test whiskey",
            # Palate data present
            "palate_flavors": ["vanilla", "oak"],
            "palate_description": "Smooth palate",
            # Other fields
            "nose_description": "Nice nose",
            "primary_aromas": ["honey", "spice"],
            "finish_description": "Long finish",
            "best_price": 50.00,
        }

        completeness_score = pipeline._calculate_completeness(extracted_data)
        status = pipeline._determine_status(extracted_data, completeness_score)

        # With palate data and good score, should be complete
        assert status in ["complete", "verified"], \
            f"Expected complete/verified with palate, got {status} (score={completeness_score})"


class TestProductPipelineV2Integration:
    """Integration tests for V2 pipeline components."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_v2_mocks(self):
        """Test full pipeline flow with V2 components mocked."""
        # Mock V2 extractor
        mock_extractor = AsyncMock()
        mock_extractor.extract.return_value = {
            "name": "Integration Test Whiskey",
            "brand": "Test Distillery",
            "product_type": "whiskey",
            "abv": 43.0,
            "country": "Scotland",
            "region": "Speyside",
            "description": "A fine single malt",
            # Tasting profile
            "nose_description": "Honey and vanilla",
            "primary_aromas": ["honey", "vanilla", "oak"],
            "palate_description": "Smooth and complex",
            "palate_flavors": ["caramel", "dried fruit", "spice"],
            "finish_description": "Long, warming finish",
            "finish_flavors": ["oak", "smoke"],
            # Confidence scores from V2
            "field_confidences": {
                "name": 0.95,
                "brand": 0.90,
                "palate_description": 0.85,
            },
            "overall_confidence": 0.88,
        }

        with patch.object(
            UnifiedProductPipeline, '_resolve_brand', new_callable=AsyncMock
        ) as mock_brand:
            mock_brand.return_value = MagicMock(name="Test Distillery")

            with patch.object(
                UnifiedProductPipeline, '_save_product', new_callable=AsyncMock
            ) as mock_save:
                mock_product = MagicMock()
                mock_product.id = uuid.uuid4()
                mock_save.return_value = mock_product

                pipeline = UnifiedProductPipeline(
                    ai_extractor=mock_extractor,
                    smart_crawler=MagicMock()
                )

                result = await pipeline.process_url(
                    "https://example.com/whiskey/integration-test",
                    {
                        "source": "iwsc",
                        "year": 2024,
                        "product_type_hint": "whiskey",
                    }
                )

                assert result.success
                assert result.product_id is not None
                # V2 provides field confidence scores
                assert "field_confidences" in result.extracted_data
                assert result.extracted_data["field_confidences"]["name"] == 0.95
