"""
Unit tests for Competition V2 components.

Tests Phase 7: Competition Flow Update - unit tests for AIExtractorV2
and CompetitionOrchestratorV2.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from crawler.services.quality_gate_v2 import ProductStatus


# Test AIExtractorV2 unit tests
class TestAIExtractorV2Unit:
    """Unit tests for AIExtractorV2."""

    def test_default_initialization(self):
        """Test default initialization creates AI client."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()
        assert extractor.ai_client is not None

    def test_custom_client_injection(self):
        """Test custom AI client can be injected."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        mock_client = Mock()
        extractor = AIExtractorV2(ai_client=mock_client)
        assert extractor.ai_client is mock_client

    def test_infer_category_iwsc(self):
        """Test category inference for IWSC source."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()
        category = extractor._infer_category(
            context={"source": "iwsc"},
            product_type="whiskey"
        )
        assert category == "single_malt"

    def test_infer_category_sfwsc(self):
        """Test category inference for SFWSC source."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()
        category = extractor._infer_category(
            context={"source": "sfwsc"},
            product_type="whiskey"
        )
        assert category == "bourbon"

    def test_infer_category_dwwa_port(self):
        """Test category inference for DWWA port wine."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()
        category = extractor._infer_category(
            context={"source": "dwwa"},
            product_type="port_wine"
        )
        assert category == "tawny"

    def test_infer_category_unknown_source(self):
        """Test category inference returns None for unknown source."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()
        category = extractor._infer_category(
            context={"source": "unknown_competition"},
            product_type="whiskey"
        )
        assert category is None


class TestAIExtractorV2Singleton:
    """Tests for AIExtractorV2 singleton pattern."""

    def test_get_ai_extractor_v2_returns_instance(self):
        """Test getter returns an instance."""
        from crawler.discovery.extractors.ai_extractor_v2 import (
            get_ai_extractor_v2,
            reset_ai_extractor_v2,
        )

        reset_ai_extractor_v2()
        extractor = get_ai_extractor_v2()
        assert extractor is not None

    def test_get_ai_extractor_v2_returns_same_instance(self):
        """Test getter returns same instance on multiple calls."""
        from crawler.discovery.extractors.ai_extractor_v2 import (
            get_ai_extractor_v2,
            reset_ai_extractor_v2,
        )

        reset_ai_extractor_v2()
        extractor1 = get_ai_extractor_v2()
        extractor2 = get_ai_extractor_v2()
        assert extractor1 is extractor2

    def test_reset_ai_extractor_v2(self):
        """Test reset clears singleton instance."""
        from crawler.discovery.extractors.ai_extractor_v2 import (
            get_ai_extractor_v2,
            reset_ai_extractor_v2,
        )

        extractor1 = get_ai_extractor_v2()
        reset_ai_extractor_v2()
        extractor2 = get_ai_extractor_v2()
        assert extractor1 is not extractor2


# Test CompetitionOrchestratorV2 unit tests
class TestCompetitionOrchestratorV2Unit:
    """Unit tests for CompetitionOrchestratorV2."""

    def test_default_initialization(self):
        """Test default initialization creates components."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()
        assert orchestrator.ai_extractor is not None
        assert orchestrator.quality_gate is not None

    def test_custom_component_injection(self):
        """Test custom components can be injected."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        mock_extractor = Mock()
        mock_quality_gate = Mock()

        orchestrator = CompetitionOrchestratorV2(
            ai_extractor=mock_extractor,
            quality_gate=mock_quality_gate,
        )

        assert orchestrator.ai_extractor is mock_extractor
        assert orchestrator.quality_gate is mock_quality_gate

    def test_should_enrich_skeleton(self):
        """Test skeleton products need enrichment."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.SKELETON) is True

    def test_should_enrich_partial(self):
        """Test partial products need enrichment."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.PARTIAL) is True

    def test_should_not_enrich_complete(self):
        """Test complete products don't need enrichment."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.COMPLETE) is False

    def test_should_not_enrich_enriched(self):
        """Test enriched products don't need enrichment."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.ENRICHED) is False

    def test_should_not_enrich_rejected(self):
        """Test rejected products don't need enrichment."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.REJECTED) is False


class TestCompetitionOrchestratorV2Singleton:
    """Tests for CompetitionOrchestratorV2 singleton pattern."""

    def test_get_competition_orchestrator_v2_returns_instance(self):
        """Test getter returns an instance."""
        from crawler.services.competition_orchestrator_v2 import (
            get_competition_orchestrator_v2,
            reset_competition_orchestrator_v2,
        )

        reset_competition_orchestrator_v2()
        orchestrator = get_competition_orchestrator_v2()
        assert orchestrator is not None

    def test_get_competition_orchestrator_v2_returns_same_instance(self):
        """Test getter returns same instance on multiple calls."""
        from crawler.services.competition_orchestrator_v2 import (
            get_competition_orchestrator_v2,
            reset_competition_orchestrator_v2,
        )

        reset_competition_orchestrator_v2()
        orchestrator1 = get_competition_orchestrator_v2()
        orchestrator2 = get_competition_orchestrator_v2()
        assert orchestrator1 is orchestrator2

    def test_reset_competition_orchestrator_v2(self):
        """Test reset clears singleton instance."""
        from crawler.services.competition_orchestrator_v2 import (
            get_competition_orchestrator_v2,
            reset_competition_orchestrator_v2,
        )

        orchestrator1 = get_competition_orchestrator_v2()
        reset_competition_orchestrator_v2()
        orchestrator2 = get_competition_orchestrator_v2()
        assert orchestrator1 is not orchestrator2


# Test Result dataclasses
class TestCompetitionExtractionResult:
    """Tests for CompetitionExtractionResult dataclass."""

    def test_default_values(self):
        """Test default values for CompetitionExtractionResult."""
        from crawler.services.competition_orchestrator_v2 import CompetitionExtractionResult

        result = CompetitionExtractionResult(success=True)
        assert result.success is True
        assert result.product_data is None
        assert result.quality_status is None
        assert result.needs_enrichment is False
        assert result.error is None
        assert result.field_confidences == {}
        assert result.award_data is None
        assert result.source_url is None

    def test_with_all_values(self):
        """Test CompetitionExtractionResult with all values set."""
        from crawler.services.competition_orchestrator_v2 import CompetitionExtractionResult

        result = CompetitionExtractionResult(
            success=True,
            product_data={"name": "Test Whiskey"},
            quality_status="complete",
            needs_enrichment=False,
            award_data={"medal": "Gold", "year": 2024},
            source_url="https://example.com/product",
        )
        assert result.success is True
        assert result.product_data["name"] == "Test Whiskey"
        assert result.award_data["medal"] == "Gold"


class TestCompetitionBatchResult:
    """Tests for CompetitionBatchResult dataclass."""

    def test_default_values(self):
        """Test default values for CompetitionBatchResult."""
        from crawler.services.competition_orchestrator_v2 import CompetitionBatchResult

        result = CompetitionBatchResult(success=True)
        assert result.success is True
        assert result.total_processed == 0
        assert result.successful == 0
        assert result.failed == 0
        assert result.needs_enrichment == 0
        assert result.complete == 0
        assert result.errors == []
        assert result.results == []


# Test async extraction flow
class TestAsyncExtractionFlow:
    """Async tests for extraction flow."""

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_extract_with_context_hints(self):
        """Test extraction uses context hints."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()

        mock_data = {
            "name": "Test Product",
            "brand": "Test Brand",
            "abv": 40.0,
        }

        with patch.object(extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html>content</html>"

            with patch.object(extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                mock_result.products = [Mock(
                    extracted_data=mock_data,
                    confidence=0.9,
                    field_confidences={"name": 0.95}
                )]
                mock_extract.return_value = mock_result

                result = await extractor.extract(
                    url="https://test.com/product",
                    context={
                        "source": "test",
                        "year": 2024,
                        "medal_hint": "Gold",
                        "score_hint": "95",
                    }
                )

        # Medal hint should be added if not in extracted data
        assert result.get("award_medal") == "Gold"
        assert result.get("award_score") == 95

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_batch_processing(self):
        """Test batch URL processing."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()

        urls = [
            {"url": "https://test.com/product1", "medal_hint": "Gold"},
            {"url": "https://test.com/product2", "medal_hint": "Silver"},
        ]

        mock_data = {"name": "Test", "brand": "Brand", "abv": 40.0}

        with patch.object(orchestrator.ai_extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html>content</html>"

            with patch.object(orchestrator.ai_extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                mock_result.products = [Mock(
                    extracted_data=mock_data,
                    confidence=0.9,
                    field_confidences={"name": 0.95, "brand": 0.9, "abv": 0.85}
                )]
                mock_extract.return_value = mock_result

                result = await orchestrator.process_competition_batch(
                    urls=urls,
                    source="test",
                    year=2024,
                    product_type="whiskey",
                )

        assert result.total_processed == 2
        assert result.successful == 2
        assert len(result.results) == 2
