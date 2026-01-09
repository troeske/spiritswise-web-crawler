"""
Integration tests for Competition Orchestrator V2.

Tests Phase 7: Competition Flow Update with V2 components.
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock, MagicMock

from crawler.services.quality_gate_v2 import ProductStatus


# Fixtures
@pytest.fixture
def sample_iwsc_html():
    """Sample IWSC-style HTML for extraction."""
    return """
    <html>
    <head><title>IWSC Gold Medal Winner - Glenfiddich 18</title></head>
    <body>
        <div class="product-detail">
            <h1>Glenfiddich 18 Year Old Single Malt</h1>
            <div class="medal-badge">Gold Medal 2024</div>
            <div class="score">95/100</div>
            <div class="producer">William Grant & Sons</div>
            <div class="country">Scotland</div>
            <div class="region">Speyside</div>
            <div class="abv">40%</div>
            <div class="description">
                An elegant and complex whisky with notes of dried fruit,
                oak, and a hint of smoke.
            </div>
            <div class="tasting-notes">
                <p class="nose">Rich dried fruits, oak, vanilla</p>
                <p class="palate">Honey, cinnamon, gentle smoke</p>
                <p class="finish">Long and warming with oak notes</p>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def sample_sfwsc_html():
    """Sample SFWSC-style HTML for extraction."""
    return """
    <html>
    <head><title>SFWSC Double Gold - Maker's Mark</title></head>
    <body>
        <div class="winner-card">
            <h1>Maker's Mark Kentucky Straight Bourbon</h1>
            <span class="award">Double Gold Medal</span>
            <span class="competition">San Francisco World Spirits Competition 2024</span>
            <div class="details">
                <span class="producer">Beam Suntory</span>
                <span class="type">Bourbon Whiskey</span>
                <span class="abv">45%</span>
                <span class="country">USA</span>
                <span class="region">Kentucky</span>
            </div>
            <div class="review">
                <p>A smooth, approachable bourbon with caramel and vanilla notes.</p>
            </div>
        </div>
    </body>
    </html>
    """


@pytest.fixture
def mock_ai_response_iwsc():
    """Mock AI extraction response for IWSC product."""
    return {
        "products": [
            {
                "name": "Glenfiddich 18 Year Old Single Malt",
                "brand": "Glenfiddich",
                "abv": 40.0,
                "product_type": "whiskey",
                "product_category": "single_malt",
                "country": "Scotland",
                "region": "Speyside",
                "description": "An elegant and complex whisky with notes of dried fruit, oak, and a hint of smoke.",
                "nose_description": "Rich dried fruits, oak, vanilla",
                "palate_description": "Honey, cinnamon, gentle smoke",
                "finish_description": "Long and warming with oak notes",
                "confidence": 0.92
            }
        ],
        "field_confidences": {
            "name": 0.95,
            "brand": 0.90,
            "abv": 0.92,
            "description": 0.85
        }
    }


@pytest.fixture
def mock_ai_response_sfwsc():
    """Mock AI extraction response for SFWSC product."""
    return {
        "products": [
            {
                "name": "Maker's Mark Kentucky Straight Bourbon",
                "brand": "Maker's Mark",
                "abv": 45.0,
                "product_type": "whiskey",
                "product_category": "bourbon",
                "country": "USA",
                "region": "Kentucky",
                "description": "A smooth, approachable bourbon with caramel and vanilla notes.",
                "confidence": 0.88
            }
        ],
        "field_confidences": {
            "name": 0.95,
            "brand": 0.90,
            "abv": 0.88,
            "description": 0.82
        }
    }


# Test AIExtractorV2 class
class TestAIExtractorV2:
    """Tests for AIExtractorV2 that uses V2 components."""

    def test_extractor_v2_exists(self):
        """Test AIExtractorV2 can be imported."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2
        extractor = AIExtractorV2()
        assert extractor is not None

    def test_extractor_v2_uses_ai_client_v2(self):
        """Test AIExtractorV2 uses AIClientV2 internally."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()
        assert hasattr(extractor, 'ai_client')

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_extract_iwsc_product(self, sample_iwsc_html, mock_ai_response_iwsc):
        """Test extraction from IWSC-style content."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()

        # Mock the fetch and AI client
        with patch.object(extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_iwsc_html

            with patch.object(extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                mock_result.products = [Mock(
                    extracted_data=mock_ai_response_iwsc["products"][0],
                    confidence=0.92,
                    field_confidences=mock_ai_response_iwsc["field_confidences"]
                )]
                mock_extract.return_value = mock_result

                result = await extractor.extract(
                    url="https://iwsc.net/product/123",
                    context={"source": "iwsc", "year": 2024, "medal_hint": "Gold"}
                )

        assert result is not None
        assert "name" in result
        assert "abv" in result

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_extract_sfwsc_product(self, sample_sfwsc_html, mock_ai_response_sfwsc):
        """Test extraction from SFWSC-style content."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()

        with patch.object(extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_sfwsc_html

            with patch.object(extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                mock_result.products = [Mock(
                    extracted_data=mock_ai_response_sfwsc["products"][0],
                    confidence=0.88,
                    field_confidences=mock_ai_response_sfwsc["field_confidences"]
                )]
                mock_extract.return_value = mock_result

                result = await extractor.extract(
                    url="https://sfwsc.com/winner/456",
                    context={"source": "sfwsc", "year": 2024, "medal_hint": "Double Gold"}
                )

        assert result is not None
        assert "name" in result


# Test Award Data Extraction
class TestAwardDataExtraction:
    """Tests for extracting award-specific data."""

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_extract_award_medal(self, sample_iwsc_html, mock_ai_response_iwsc):
        """Test medal information is extracted."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()

        with patch.object(extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_iwsc_html

            with patch.object(extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                # Include award data
                product_data = mock_ai_response_iwsc["products"][0].copy()
                product_data["award_medal"] = "Gold"
                product_data["award_year"] = 2024
                mock_result.products = [Mock(
                    extracted_data=product_data,
                    confidence=0.92,
                    field_confidences=mock_ai_response_iwsc["field_confidences"]
                )]
                mock_extract.return_value = mock_result

                result = await extractor.extract(
                    url="https://iwsc.net/product/123",
                    context={"source": "iwsc", "year": 2024, "medal_hint": "Gold"}
                )

        # Medal info should be available
        assert result is not None

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_extract_award_score(self, sample_iwsc_html, mock_ai_response_iwsc):
        """Test score information is extracted when available."""
        from crawler.discovery.extractors.ai_extractor_v2 import AIExtractorV2

        extractor = AIExtractorV2()

        with patch.object(extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_iwsc_html

            with patch.object(extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                product_data = mock_ai_response_iwsc["products"][0].copy()
                product_data["award_score"] = 95
                mock_result.products = [Mock(
                    extracted_data=product_data,
                    confidence=0.92,
                    field_confidences=mock_ai_response_iwsc["field_confidences"]
                )]
                mock_extract.return_value = mock_result

                result = await extractor.extract(
                    url="https://iwsc.net/product/123",
                    context={"source": "iwsc", "year": 2024, "score_hint": "95"}
                )

        assert result is not None


# Test Quality Gate Integration
class TestQualityGateIntegration:
    """Tests for quality gate integration in competition flow."""

    @pytest.mark.django_db
    def test_assess_competition_product_quality(self):
        """Test quality assessment for competition-extracted products."""
        from crawler.services.quality_gate_v2 import QualityGateV2

        quality_gate = QualityGateV2()

        # Competition product with full data
        product_data = {
            "name": "Glenfiddich 18",
            "brand": "Glenfiddich",
            "abv": 40.0,
            "description": "A complex whisky",
            "region": "Speyside",
            "country": "Scotland",
        }
        field_confidences = {
            "name": 0.95,
            "brand": 0.90,
            "abv": 0.88,
            "description": 0.85,
        }

        assessment = quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey",
            field_confidences=field_confidences,
        )

        # Should be at least PARTIAL (has name, brand, abv, description)
        assert assessment.status in [ProductStatus.PARTIAL, ProductStatus.COMPLETE]

    @pytest.mark.django_db
    def test_assess_skeleton_competition_product(self):
        """Test quality assessment for skeleton competition products."""
        from crawler.services.quality_gate_v2 import QualityGateV2

        quality_gate = QualityGateV2()

        # Skeleton product - only name from competition list
        product_data = {
            "name": "Mystery Award Winner",
        }
        field_confidences = {
            "name": 0.9,
        }

        assessment = quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey",
            field_confidences=field_confidences,
        )

        # Should be SKELETON (has name but missing critical fields)
        assert assessment.status == ProductStatus.SKELETON

    @pytest.mark.django_db
    def test_competition_product_needs_enrichment(self):
        """Test enrichment decision for competition products."""
        from crawler.services.quality_gate_v2 import QualityGateV2

        quality_gate = QualityGateV2()

        # Partial product - has name and brand but no ABV
        product_data = {
            "name": "Award Winner Bourbon",
            "brand": "Some Distillery",
        }
        field_confidences = {
            "name": 0.9,
            "brand": 0.85,
        }

        assessment = quality_gate.assess(
            extracted_data=product_data,
            product_type="whiskey",
            field_confidences=field_confidences,
        )

        # Should need enrichment
        assert assessment.needs_enrichment is True


# Test CompetitionOrchestratorV2
class TestCompetitionOrchestratorV2:
    """Tests for Competition Orchestrator with V2 integration."""

    def test_orchestrator_v2_initialization(self):
        """Test CompetitionOrchestratorV2 can be initialized."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()
        assert orchestrator is not None
        assert hasattr(orchestrator, 'ai_extractor')
        assert hasattr(orchestrator, 'quality_gate')

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_process_competition_url_with_v2(self, sample_iwsc_html, mock_ai_response_iwsc):
        """Test processing a single competition URL with V2 components."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()

        with patch.object(orchestrator.ai_extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_iwsc_html

            with patch.object(orchestrator.ai_extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                mock_result.products = [Mock(
                    extracted_data=mock_ai_response_iwsc["products"][0],
                    confidence=0.92,
                    field_confidences=mock_ai_response_iwsc["field_confidences"]
                )]
                mock_extract.return_value = mock_result

                result = await orchestrator.process_competition_url(
                    url="https://iwsc.net/product/123",
                    source="iwsc",
                    year=2024,
                    medal_hint="Gold",
                    product_type="whiskey",
                )

        assert result is not None
        assert result.success is True
        assert result.product_data is not None

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_quality_assessment_in_flow(self, sample_iwsc_html, mock_ai_response_iwsc):
        """Test quality assessment is performed in competition flow."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()

        with patch.object(orchestrator.ai_extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_iwsc_html

            with patch.object(orchestrator.ai_extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                mock_result.products = [Mock(
                    extracted_data=mock_ai_response_iwsc["products"][0],
                    confidence=0.92,
                    field_confidences=mock_ai_response_iwsc["field_confidences"]
                )]
                mock_extract.return_value = mock_result

                result = await orchestrator.process_competition_url(
                    url="https://iwsc.net/product/123",
                    source="iwsc",
                    year=2024,
                    medal_hint="Gold",
                    product_type="whiskey",
                )

        # Should have quality status
        assert result.quality_status is not None
        assert result.quality_status in [s.value for s in ProductStatus]

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_enrichment_decision_in_flow(self, sample_iwsc_html):
        """Test enrichment decision is made in competition flow."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()

        # Incomplete data - should trigger enrichment
        incomplete_data = {
            "name": "Award Winner",
            "brand": "Unknown Brand",
            # No ABV - critical field missing
        }

        with patch.object(orchestrator.ai_extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html>minimal content</html>"

            with patch.object(orchestrator.ai_extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                mock_result.products = [Mock(
                    extracted_data=incomplete_data,
                    confidence=0.6,
                    field_confidences={"name": 0.9, "brand": 0.7}
                )]
                mock_extract.return_value = mock_result

                result = await orchestrator.process_competition_url(
                    url="https://competition.com/product/789",
                    source="generic",
                    year=2024,
                    medal_hint="Gold",
                    product_type="whiskey",
                )

        # Should indicate needs enrichment
        assert result.needs_enrichment is True


# Test Error Handling
class TestErrorHandling:
    """Tests for error handling in competition V2 flow."""

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_handles_fetch_failure(self):
        """Test graceful handling of content fetch failure."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()

        with patch.object(orchestrator.ai_extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Connection refused")

            result = await orchestrator.process_competition_url(
                url="https://broken.example.com/product",
                source="unknown",
                year=2024,
                medal_hint="Gold",
                product_type="whiskey",
            )

        assert result.success is False
        assert result.error is not None

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_handles_extraction_failure(self, sample_iwsc_html):
        """Test graceful handling of AI extraction failure."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()

        with patch.object(orchestrator.ai_extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_iwsc_html

            with patch.object(orchestrator.ai_extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = False
                mock_result.error = "AI service unavailable"
                mock_result.products = []
                mock_extract.return_value = mock_result

                result = await orchestrator.process_competition_url(
                    url="https://iwsc.net/product/123",
                    source="iwsc",
                    year=2024,
                    medal_hint="Gold",
                    product_type="whiskey",
                )

        assert result.success is False


# Test Award Preservation
class TestAwardPreservation:
    """Tests for preserving award data through extraction."""

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_medal_preserved_in_result(self, sample_iwsc_html, mock_ai_response_iwsc):
        """Test medal information is preserved in result."""
        from crawler.services.competition_orchestrator_v2 import CompetitionOrchestratorV2

        orchestrator = CompetitionOrchestratorV2()

        with patch.object(orchestrator.ai_extractor, '_fetch_content', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = sample_iwsc_html

            with patch.object(orchestrator.ai_extractor.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_result = Mock()
                mock_result.success = True
                mock_result.products = [Mock(
                    extracted_data=mock_ai_response_iwsc["products"][0],
                    confidence=0.92,
                    field_confidences=mock_ai_response_iwsc["field_confidences"]
                )]
                mock_extract.return_value = mock_result

                result = await orchestrator.process_competition_url(
                    url="https://iwsc.net/product/123",
                    source="iwsc",
                    year=2024,
                    medal_hint="Gold",
                    product_type="whiskey",
                )

        # Award data should be included
        assert result.award_data is not None
        assert result.award_data.get("medal") == "Gold"
        assert result.award_data.get("competition") == "IWSC"
        assert result.award_data.get("year") == 2024
