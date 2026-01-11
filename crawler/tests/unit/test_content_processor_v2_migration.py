"""
Tests for content_processor.py V1→V2 migration.

Task 1.7: Verify that content_processor.py uses V2 AI client components:
- AIClientV2 instead of V1 AIEnhancementClient
- EnhancementResult from ai_client_v2 (V1-compatible wrapper)
- get_ai_client_v2 instead of get_ai_client

TDD Approach: These tests verify the migration is complete.
"""

import pytest
import inspect
from unittest.mock import MagicMock, patch, AsyncMock


class TestContentProcessorUsesV2Client:
    """Test that content_processor.py uses V2 AI client components."""

    def test_imports_v2_ai_client(self):
        """
        Verify content_processor.py imports from ai_client_v2.

        After migration, the import should be from ai_client_v2, not ai_client.
        """
        import crawler.services.content_processor as module

        source = inspect.getsource(module)

        # Check that V2 import exists
        assert "from crawler.services.ai_client_v2 import" in source, (
            "content_processor.py should import from ai_client_v2"
        )

    def test_v1_ai_client_not_directly_imported(self):
        """
        Verify content_processor.py does NOT import V1 ai_client directly.

        After migration, there should be no direct import from ai_client.
        """
        import crawler.services.content_processor as module

        source = inspect.getsource(module)

        # V1 direct import should NOT exist
        v1_import = "from crawler.services.ai_client import AIEnhancementClient"
        assert v1_import not in source, (
            "content_processor.py should NOT import V1 AIEnhancementClient directly"
        )

    def test_enhancement_result_from_v2(self):
        """
        Verify EnhancementResult is imported from ai_client_v2.
        """
        import crawler.services.content_processor as module

        source = inspect.getsource(module)

        # Should import EnhancementResult from V2
        assert "EnhancementResult" in source
        assert "from crawler.services.ai_client_v2" in source


class TestContentProcessorClientType:
    """Test that ContentProcessor uses V2 client type."""

    def test_content_processor_uses_v2_client_type(self):
        """
        Verify ContentProcessor.ai_client is of type AIClientV2.
        """
        from crawler.services.content_processor import ContentProcessor
        from crawler.services.ai_client_v2 import AIClientV2

        # Create processor with mocked client
        mock_client = MagicMock(spec=AIClientV2)
        processor = ContentProcessor(ai_client=mock_client)

        assert processor.ai_client == mock_client

    def test_default_client_is_v2(self):
        """
        Verify ContentProcessor uses get_ai_client (alias for get_ai_client_v2) for default client.
        """
        import crawler.services.content_processor as module
        import inspect

        source = inspect.getsource(module)

        # The alias get_ai_client should be used which points to get_ai_client_v2
        assert "get_ai_client = get_ai_client_v2" in source or "get_ai_client_v2" in source, (
            "content_processor should use get_ai_client_v2 or its alias"
        )

        # Also verify the class uses it
        class_source = inspect.getsource(module.ContentProcessor)
        # Check that __init__ uses get_ai_client (the alias)
        assert "get_ai_client" in class_source, (
            "ContentProcessor.__init__ should call get_ai_client for default client"
        )


class TestContentProcessorEnhanceMethod:
    """Test that enhance_from_crawler method works with V2."""

    @pytest.mark.asyncio
    async def test_enhance_from_crawler_method_exists_on_v2_client(self):
        """
        Verify AIClientV2 has enhance_from_crawler method for backward compatibility.
        """
        from crawler.services.ai_client_v2 import AIClientV2

        client = AIClientV2()
        assert hasattr(client, 'enhance_from_crawler'), (
            "AIClientV2 must have enhance_from_crawler method for backward compatibility"
        )
        assert callable(client.enhance_from_crawler)

    @pytest.mark.asyncio
    async def test_enhance_from_crawler_returns_enhancement_result(self):
        """
        Verify enhance_from_crawler returns EnhancementResult.
        """
        from crawler.services.ai_client_v2 import AIClientV2, EnhancementResult

        # Mock the extract method
        with patch.object(AIClientV2, 'extract') as mock_extract:
            from crawler.services.ai_client_v2 import ExtractionResultV2, ExtractedProductV2

            mock_extract.return_value = ExtractionResultV2(
                success=True,
                products=[
                    ExtractedProductV2(
                        extracted_data={'name': 'Test Whisky', 'abv': '40%'},
                        product_type='whiskey',
                        confidence=0.85,
                        field_confidences={'name': 0.9, 'abv': 0.8},
                    )
                ],
                processing_time_ms=150.0,
            )

            client = AIClientV2()
            result = await client.enhance_from_crawler(
                content="<html>Test content</html>",
                source_url="https://example.com/whisky",
                product_type_hint="whiskey",
            )

            assert isinstance(result, EnhancementResult)
            assert result.success is True
            assert result.product_type == 'whiskey'
            assert result.confidence == 0.85
            assert result.extracted_data['name'] == 'Test Whisky'
            assert result.field_confidences == {'name': 0.9, 'abv': 0.8}


class TestServicesModuleExports:
    """Test that services __init__.py exports correct types."""

    def test_services_module_exports_ai_enhancement_client(self):
        """
        Verify services module exports AIEnhancementClient alias.
        """
        from crawler.services import AIEnhancementClient
        from crawler.services.ai_client_v2 import AIClientV2

        # AIEnhancementClient should be alias for AIClientV2
        assert AIEnhancementClient is AIClientV2

    def test_services_module_exports_get_ai_client(self):
        """
        Verify services module exports get_ai_client alias.
        """
        from crawler.services import get_ai_client
        from crawler.services.ai_client_v2 import get_ai_client_v2

        # get_ai_client should be alias for get_ai_client_v2
        assert get_ai_client is get_ai_client_v2

    def test_services_module_exports_enhancement_result(self):
        """
        Verify services module exports EnhancementResult.
        """
        from crawler.services import EnhancementResult
        from crawler.services.ai_client_v2 import EnhancementResult as V2EnhancementResult

        assert EnhancementResult is V2EnhancementResult
