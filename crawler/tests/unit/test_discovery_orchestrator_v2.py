"""
Unit tests for DiscoveryOrchestratorV2.

Tests Phase 5: Discovery Orchestrator V2 unit tests.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock

from crawler.services.discovery_orchestrator_v2 import (
    DiscoveryOrchestratorV2,
    SingleProductResult,
    ListProductResult,
    get_discovery_orchestrator_v2,
    reset_discovery_orchestrator_v2,
)
from crawler.services.quality_gate_v2 import ProductStatus


class TestSingleProductResult:
    """Tests for SingleProductResult dataclass."""

    def test_default_values(self):
        """Test default values for SingleProductResult."""
        result = SingleProductResult(success=True)
        assert result.success is True
        assert result.product_data is None
        assert result.quality_status is None
        assert result.needs_enrichment is False
        assert result.error is None
        assert result.product_id is None
        assert result.field_confidences == {}
        assert result.detail_url is None

    def test_with_all_values(self):
        """Test SingleProductResult with all values set."""
        result = SingleProductResult(
            success=True,
            product_data={"name": "Test"},
            quality_status="complete",
            needs_enrichment=False,
            error=None,
            product_id=123,
            field_confidences={"name": 0.95},
            detail_url="https://example.com/product"
        )
        assert result.success is True
        assert result.product_data == {"name": "Test"}
        assert result.quality_status == "complete"
        assert result.product_id == 123

    def test_failure_result(self):
        """Test SingleProductResult for failure case."""
        result = SingleProductResult(
            success=False,
            error="Connection failed"
        )
        assert result.success is False
        assert result.error == "Connection failed"


class TestListProductResult:
    """Tests for ListProductResult dataclass."""

    def test_default_values(self):
        """Test default values for ListProductResult."""
        result = ListProductResult(success=True)
        assert result.success is True
        assert result.products == []
        assert result.error is None
        assert result.source_url is None

    def test_with_products(self):
        """Test ListProductResult with products."""
        products = [
            SingleProductResult(success=True, product_data={"name": "Product 1"}),
            SingleProductResult(success=True, product_data={"name": "Product 2"}),
        ]
        result = ListProductResult(
            success=True,
            products=products,
            source_url="https://example.com/list"
        )
        assert len(result.products) == 2
        assert result.source_url == "https://example.com/list"


class TestDiscoveryOrchestratorV2Init:
    """Tests for DiscoveryOrchestratorV2 initialization."""

    def test_default_initialization(self):
        """Test default initialization creates all components."""
        orchestrator = DiscoveryOrchestratorV2()
        assert orchestrator.ai_client is not None
        assert orchestrator.quality_gate is not None
        assert orchestrator.enrichment_orchestrator is not None
        assert orchestrator.source_tracker is not None

    def test_custom_components(self):
        """Test initialization with custom components."""
        mock_ai_client = Mock()
        mock_quality_gate = Mock()
        mock_enrichment = Mock()
        mock_source_tracker = Mock()

        orchestrator = DiscoveryOrchestratorV2(
            ai_client=mock_ai_client,
            quality_gate=mock_quality_gate,
            enrichment_orchestrator=mock_enrichment,
            source_tracker=mock_source_tracker,
        )

        assert orchestrator.ai_client is mock_ai_client
        assert orchestrator.quality_gate is mock_quality_gate
        assert orchestrator.enrichment_orchestrator is mock_enrichment
        assert orchestrator.source_tracker is mock_source_tracker


class TestShouldEnrich:
    """Tests for _should_enrich method."""

    def test_skeleton_needs_enrichment(self):
        """Test skeleton status needs enrichment."""
        orchestrator = DiscoveryOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.SKELETON.value) is True

    def test_partial_needs_enrichment(self):
        """Test partial status needs enrichment."""
        orchestrator = DiscoveryOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.PARTIAL.value) is True

    def test_complete_no_enrichment(self):
        """Test complete status doesn't need enrichment."""
        orchestrator = DiscoveryOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.COMPLETE.value) is False

    def test_enriched_no_enrichment(self):
        """Test enriched status doesn't need enrichment."""
        orchestrator = DiscoveryOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.ENRICHED.value) is False

    def test_rejected_no_enrichment(self):
        """Test rejected status doesn't need enrichment."""
        orchestrator = DiscoveryOrchestratorV2()
        assert orchestrator._should_enrich(ProductStatus.REJECTED.value) is False

    def test_unknown_status_no_enrichment(self):
        """Test unknown status defaults to no enrichment."""
        orchestrator = DiscoveryOrchestratorV2()
        assert orchestrator._should_enrich("unknown") is False


class TestResolveUrl:
    """Tests for _resolve_url method."""

    def test_resolve_relative_url(self):
        """Test resolving relative URL to absolute."""
        orchestrator = DiscoveryOrchestratorV2()
        result = orchestrator._resolve_url(
            base_url="https://example.com/products",
            relative_url="/details/123"
        )
        assert result == "https://example.com/details/123"

    def test_resolve_already_absolute(self):
        """Test absolute URL is returned unchanged."""
        orchestrator = DiscoveryOrchestratorV2()
        result = orchestrator._resolve_url(
            base_url="https://example.com",
            relative_url="https://other.com/product"
        )
        assert result == "https://other.com/product"

    def test_resolve_none_url(self):
        """Test None URL returns None."""
        orchestrator = DiscoveryOrchestratorV2()
        result = orchestrator._resolve_url(
            base_url="https://example.com",
            relative_url=None
        )
        assert result is None

    def test_resolve_path_only(self):
        """Test resolving path-only relative URL."""
        orchestrator = DiscoveryOrchestratorV2()
        result = orchestrator._resolve_url(
            base_url="https://example.com/list/",
            relative_url="product.html"
        )
        assert result == "https://example.com/list/product.html"


class TestAssessQuality:
    """Tests for _assess_quality method."""

    @pytest.mark.django_db
    def test_assess_quality_with_complete_data(self):
        """Test quality assessment with complete data."""
        orchestrator = DiscoveryOrchestratorV2()

        product_data = {
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "abv": 40.0,
            "description": "A fine whiskey"
        }
        field_confidences = {
            "name": 0.95,
            "brand": 0.90,
            "abv": 0.88,
            "description": 0.85
        }

        status = orchestrator._assess_quality(
            product_data=product_data,
            field_confidences=field_confidences,
            product_type="whiskey"
        )

        # Should be at least partial since all core fields present
        assert status in [
            ProductStatus.COMPLETE.value,
            ProductStatus.PARTIAL.value
        ]

    @pytest.mark.django_db
    def test_assess_quality_without_name_is_rejected(self):
        """Test quality assessment without name results in rejection."""
        orchestrator = DiscoveryOrchestratorV2()

        product_data = {
            "brand": "Test Brand",
            "abv": 40.0,
        }
        field_confidences = {"brand": 0.9, "abv": 0.8}

        status = orchestrator._assess_quality(
            product_data=product_data,
            field_confidences=field_confidences,
            product_type="whiskey"
        )

        assert status == ProductStatus.REJECTED.value

    @pytest.mark.django_db
    def test_assess_quality_with_low_confidence(self):
        """Test quality assessment with low confidence fields."""
        orchestrator = DiscoveryOrchestratorV2()

        product_data = {
            "name": "Maybe Whiskey",
            "brand": "Unsure Brand",
        }
        # Low confidence makes fields count as missing
        field_confidences = {
            "name": 0.9,  # High confidence for name (required)
            "brand": 0.3,  # Low confidence (< 0.5)
        }

        status = orchestrator._assess_quality(
            product_data=product_data,
            field_confidences=field_confidences,
            product_type="whiskey"
        )

        # Should be skeleton since brand has low confidence
        assert status in [
            ProductStatus.SKELETON.value,
            ProductStatus.PARTIAL.value,
        ]


class TestSingletonPattern:
    """Tests for singleton pattern."""

    def test_get_discovery_orchestrator_v2_returns_instance(self):
        """Test getter returns an instance."""
        reset_discovery_orchestrator_v2()
        orchestrator = get_discovery_orchestrator_v2()
        assert orchestrator is not None
        assert isinstance(orchestrator, DiscoveryOrchestratorV2)

    def test_get_discovery_orchestrator_v2_returns_same_instance(self):
        """Test getter returns same instance on multiple calls."""
        reset_discovery_orchestrator_v2()
        orchestrator1 = get_discovery_orchestrator_v2()
        orchestrator2 = get_discovery_orchestrator_v2()
        assert orchestrator1 is orchestrator2

    def test_reset_discovery_orchestrator_v2(self):
        """Test reset clears singleton instance."""
        orchestrator1 = get_discovery_orchestrator_v2()
        reset_discovery_orchestrator_v2()
        orchestrator2 = get_discovery_orchestrator_v2()
        assert orchestrator1 is not orchestrator2


class TestExtractSingleProductAsync:
    """Async tests for extract_single_product."""

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_successful_extraction(self):
        """Test successful single product extraction."""
        orchestrator = DiscoveryOrchestratorV2()

        mock_ai_response = Mock()
        mock_ai_response.success = True
        mock_ai_response.products = [Mock(
            extracted_data={
                "name": "Test Whiskey",
                "brand": "Test Brand",
                "abv": 40.0
            },
            confidence=0.9,
            field_confidences={"name": 0.95, "brand": 0.9, "abv": 0.85}
        )]

        with patch.object(orchestrator, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html>content</html>"
            with patch.object(orchestrator.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = mock_ai_response

                result = await orchestrator.extract_single_product(
                    url="https://example.com/product",
                    product_type="whiskey"
                )

        assert result.success is True
        assert result.product_data is not None
        assert result.product_data["name"] == "Test Whiskey"

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_extraction_failure_returns_error(self):
        """Test extraction failure returns error result."""
        orchestrator = DiscoveryOrchestratorV2()

        mock_ai_response = Mock()
        mock_ai_response.success = False
        mock_ai_response.error = "Extraction failed"
        mock_ai_response.products = []

        with patch.object(orchestrator, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html>content</html>"
            with patch.object(orchestrator.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = mock_ai_response

                result = await orchestrator.extract_single_product(
                    url="https://example.com/product",
                    product_type="whiskey"
                )

        assert result.success is False
        assert "Extraction failed" in result.error or "No products" in result.error

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_fetch_failure_returns_error(self):
        """Test page fetch failure returns error result."""
        orchestrator = DiscoveryOrchestratorV2()

        with patch.object(orchestrator, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = Exception("Connection refused")

            result = await orchestrator.extract_single_product(
                url="https://example.com/product",
                product_type="whiskey"
            )

        assert result.success is False
        assert "Connection refused" in result.error


class TestExtractListProductsAsync:
    """Async tests for extract_list_products."""

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_successful_list_extraction(self):
        """Test successful list page extraction."""
        orchestrator = DiscoveryOrchestratorV2()

        mock_ai_response = Mock()
        mock_ai_response.success = True
        mock_ai_response.products = [
            Mock(
                extracted_data={"name": "Product 1", "detail_url": "/p1"},
                confidence=0.8,
                field_confidences={"name": 0.9}
            ),
            Mock(
                extracted_data={"name": "Product 2", "detail_url": "/p2"},
                confidence=0.85,
                field_confidences={"name": 0.92}
            ),
        ]

        with patch.object(orchestrator, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html>list content</html>"
            with patch.object(orchestrator.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = mock_ai_response

                result = await orchestrator.extract_list_products(
                    url="https://example.com/products",
                    product_type="whiskey"
                )

        assert result.success is True
        assert len(result.products) == 2
        assert result.source_url == "https://example.com/products"

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_list_resolves_relative_urls(self):
        """Test list extraction resolves relative detail URLs."""
        orchestrator = DiscoveryOrchestratorV2()

        mock_ai_response = Mock()
        mock_ai_response.success = True
        mock_ai_response.products = [
            Mock(
                extracted_data={"name": "Product 1", "detail_url": "/products/123"},
                confidence=0.8,
                field_confidences={"name": 0.9}
            ),
        ]

        with patch.object(orchestrator, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html>content</html>"
            with patch.object(orchestrator.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = mock_ai_response

                result = await orchestrator.extract_list_products(
                    url="https://example.com/list",
                    product_type="whiskey"
                )

        assert result.success is True
        assert result.products[0].detail_url == "https://example.com/products/123"

    @pytest.mark.django_db
    @pytest.mark.asyncio
    async def test_empty_list_extraction(self):
        """Test extraction with no products found."""
        orchestrator = DiscoveryOrchestratorV2()

        mock_ai_response = Mock()
        mock_ai_response.success = True
        mock_ai_response.products = []

        with patch.object(orchestrator, '_fetch_page', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = "<html>no products</html>"
            with patch.object(orchestrator.ai_client, 'extract', new_callable=AsyncMock) as mock_extract:
                mock_extract.return_value = mock_ai_response

                result = await orchestrator.extract_list_products(
                    url="https://example.com/empty",
                    product_type="whiskey"
                )

        assert result.success is True
        assert len(result.products) == 0
