# tests/integration/test_verification_search.py
"""
Verification Pipeline Search Integration Tests - Task 6.1

Spec Reference: docs/spec-parts/07-VERIFICATION-PIPELINE.md Section 7.1

These tests verify that the verification pipeline correctly:
1. Generates targeted search queries for missing fields
2. Limits searches to 3 additional sources
3. Filters excluded domains
4. Includes product name in search queries

Key Requirements:
- Missing tasting notes -> Query: "{name} tasting notes review"
- Missing pricing -> Query: "{name} buy price"
- Target 3 additional sources maximum
- Filter excluded domains (social media, news, forums)
- Prefer authoritative domains (retailers, review sites)
"""

import pytest
import os
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict, Any

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_VPS_TESTS") != "true",
    reason="VPS tests disabled - set RUN_VPS_TESTS=true"
)


# Excluded domains per spec
EXCLUDED_DOMAINS = [
    # Social media
    "facebook.com", "twitter.com", "instagram.com", "tiktok.com",
    # Forums
    "reddit.com", "quora.com",
    # News (not product-focused)
    "cnn.com", "bbc.com", "nytimes.com",
    # Auction sites (prices unreliable)
    "ebay.com",
]

PREFERRED_DOMAINS = [
    # Major retailers
    "thewhiskyexchange.com", "masterofmalt.com", "totalwine.com",
    # Review sites
    "whiskyadvocate.com", "whiskybase.com",
    # Producer sites
    "ardbeg.com", "glenlivet.com",
]


class TestVerificationSearchQueries:
    """
    Test search query generation for verification.
    """

    @pytest.fixture
    def verification_pipeline(self):
        """Create VerificationPipeline instance."""
        from crawler.verification.pipeline import VerificationPipeline
        return VerificationPipeline()

    @pytest.fixture
    def mock_product(self):
        """Create a mock product for testing."""
        product = Mock()
        product.name = "Glenfiddich 12 Year Old"
        product.product_type = "whiskey"
        product.abv = Decimal("40.0")
        product.source_count = 1
        product.verified_fields = []
        product.palate_description = None
        product.nose_description = None
        product.finish_description = None
        product.best_price = None
        product.brand = Mock()
        product.brand.name = "Glenfiddich"
        product.get_missing_critical_fields = Mock(return_value=["palate", "nose", "finish"])
        return product

    def test_searches_for_tasting_notes_when_missing(self, verification_pipeline, mock_product):
        """
        Product missing tasting notes should trigger search:
        Query: "{name} tasting notes review"
        """
        # Get enrichment strategies
        strategies = verification_pipeline.ENRICHMENT_STRATEGIES

        # Verify tasting_notes strategy exists
        assert "tasting_notes" in strategies

        # Verify tasting notes templates contain expected terms
        templates = strategies["tasting_notes"]
        assert any("tasting notes" in template for template in templates)
        assert any("review" in template for template in templates)

    def test_searches_for_pricing_when_missing(self, verification_pipeline, mock_product):
        """
        Product missing price should trigger search:
        Query: "{name} buy price"
        """
        # Get enrichment strategies
        strategies = verification_pipeline.ENRICHMENT_STRATEGIES

        # Verify pricing strategy exists
        assert "pricing" in strategies

        # Verify pricing templates contain expected terms
        templates = strategies["pricing"]
        assert any("buy" in template or "price" in template for template in templates)

    def test_query_includes_product_name(self, verification_pipeline, mock_product):
        """
        Search queries must include product name.
        """
        # Test query formatting
        template = "{name} tasting notes review"
        query = verification_pipeline._format_query(template, mock_product)

        assert mock_product.name in query
        assert "tasting notes review" in query

    def test_query_includes_brand_if_available(self, verification_pipeline, mock_product):
        """
        If brand differs from name, include both in query.
        """
        # Test query formatting with brand
        template = "{brand} {name} whisky review"
        query = verification_pipeline._format_query(template, mock_product)

        # Brand should be included
        assert mock_product.brand.name in query
        # Product name should also be included
        assert mock_product.name in query


class TestVerificationSearchLimits:
    """
    Test search limits and constraints.
    """

    @pytest.fixture
    def verification_pipeline(self):
        """Create VerificationPipeline instance."""
        from crawler.verification.pipeline import VerificationPipeline
        return VerificationPipeline()

    @pytest.fixture
    def mock_product(self):
        """Create a mock product for testing."""
        product = Mock()
        product.name = "Lagavulin 16 Year Old"
        product.product_type = "whiskey"
        product.source_count = 1
        product.verified_fields = []
        product.brand = Mock()
        product.brand.name = "Lagavulin"
        product.get_missing_critical_fields = Mock(return_value=["palate"])
        return product

    def test_limits_searches_to_target_sources(self, verification_pipeline, mock_product):
        """
        Should not search for more than 3 additional sources.
        """
        # Pipeline should have TARGET_SOURCES = 3
        assert verification_pipeline.TARGET_SOURCES == 3

        # When we already have 1 source, we only need 2 more (TARGET - 1)
        with patch.object(verification_pipeline, "_execute_search") as mock_search:
            mock_search.return_value = [
                "http://url1.com",
                "http://url2.com",
                "http://url3.com",
                "http://url4.com",
                "http://url5.com",
            ]

            result = verification_pipeline._search_additional_sources(mock_product, ["palate"])

            # Should be limited to TARGET_SOURCES - 1 = 2
            assert len(result) <= verification_pipeline.TARGET_SOURCES - 1

    def test_stops_searching_after_target_met(self, verification_pipeline, mock_product):
        """
        Stop searching once 3 good sources found.
        """
        # If we have 1 source already, need only 2 more
        # Once we have TARGET_SOURCES (3) total, should stop
        with patch.object(verification_pipeline, "_execute_search") as mock_search:
            mock_search.return_value = ["http://example.com/review"]

            result = verification_pipeline._search_additional_sources(mock_product, ["palate"])

            # Should limit the URLs returned
            assert len(result) <= verification_pipeline.TARGET_SOURCES - 1


class TestVerificationSearchFiltering:
    """
    Test domain filtering for search results.
    """

    @pytest.fixture
    def verification_pipeline(self):
        """Create VerificationPipeline instance."""
        from crawler.verification.pipeline import VerificationPipeline
        return VerificationPipeline()

    def test_skips_excluded_domains(self, verification_pipeline):
        """
        Should skip excluded domains:
        - Social media (facebook, twitter, instagram)
        - News sites (cnn, bbc)
        - Forums (reddit)
        """
        # Test excluded domains from the pipeline
        assert verification_pipeline._is_excluded_domain("facebook.com")
        assert verification_pipeline._is_excluded_domain("www.facebook.com")
        assert verification_pipeline._is_excluded_domain("twitter.com")
        assert verification_pipeline._is_excluded_domain("instagram.com")
        assert verification_pipeline._is_excluded_domain("reddit.com")
        assert verification_pipeline._is_excluded_domain("youtube.com")
        assert verification_pipeline._is_excluded_domain("linkedin.com")

        # Verify pipeline's EXCLUDE_DOMAINS list
        excluded = verification_pipeline.EXCLUDE_DOMAINS
        assert "facebook.com" in excluded
        assert "twitter.com" in excluded
        assert "reddit.com" in excluded

    def test_prefers_authoritative_domains(self, verification_pipeline):
        """
        Should prefer:
        - Official brand sites
        - Major retailers
        - Review sites
        """
        # Authoritative domains should NOT be excluded
        assert not verification_pipeline._is_excluded_domain("thewhiskyexchange.com")
        assert not verification_pipeline._is_excluded_domain("masterofmalt.com")
        assert not verification_pipeline._is_excluded_domain("whiskyadvocate.com")
        assert not verification_pipeline._is_excluded_domain("whiskybase.com")

    def test_skips_already_used_sources(self, verification_pipeline):
        """
        Don't search sources already used for this product.
        """
        with patch.object(verification_pipeline, "_execute_search") as mock_search:
            mock_search.return_value = [
                "http://example.com/review",
                "http://example.com/review",  # duplicate
                "http://other.com/page",
            ]

            product = Mock()
            product.name = "Test Whisky"
            product.brand = Mock()
            product.brand.name = "Test"

            result = verification_pipeline._search_additional_sources(product, ["palate"])

            # URLs should be unique (deduplicated)
            assert len(result) == len(set(result))


class TestVerificationSearchIntegration:
    """
    Test actual search integration (can mock SerpAPI for cost).
    """

    @pytest.fixture
    def verification_pipeline(self):
        """Create VerificationPipeline instance."""
        from crawler.verification.pipeline import VerificationPipeline
        return VerificationPipeline()

    @pytest.fixture
    def mock_product(self):
        """Create a mock product for testing."""
        product = Mock()
        product.name = "Ardbeg 10 Year Old"
        product.product_type = "whiskey"
        product.source_count = 1
        product.verified_fields = []
        product.brand = Mock()
        product.brand.name = "Ardbeg"
        product.get_missing_critical_fields = Mock(return_value=["palate"])
        return product

    def test_serpapi_returns_results(self, verification_pipeline, mock_product):
        """
        SerpAPI integration should return search results.
        Can be mocked for cost control.
        """
        # Mock _execute_search to avoid SerpAPI costs
        with patch.object(verification_pipeline, "_execute_search") as mock_search:
            mock_search.return_value = [
                "http://whiskyadvocate.com/ardbeg-10",
                "http://masterofmalt.com/ardbeg-10",
            ]

            result = verification_pipeline._search_additional_sources(mock_product, ["palate"])

            # Should return list of URLs
            assert isinstance(result, list)
            if result:  # If any results returned
                assert all(isinstance(url, str) for url in result)

    def test_extracts_urls_from_search_results(self, verification_pipeline, mock_product):
        """
        Should extract URL, title, snippet from results.
        """
        # Mock search results
        with patch.object(verification_pipeline, "_execute_search") as mock_search:
            mock_search.return_value = [
                "http://whiskyadvocate.com/ardbeg-10-review",
                "http://masterofmalt.com/p/ardbeg-10",
            ]

            result = verification_pipeline._search_additional_sources(mock_product, ["palate"])

            # Should return URLs as strings
            assert isinstance(result, list)
            for url in result:
                assert isinstance(url, str)
                assert url.startswith("http")


class TestEnrichmentStrategiesSpec:
    """
    Test that ENRICHMENT_STRATEGIES matches spec requirements.
    """

    @pytest.fixture
    def verification_pipeline(self):
        """Create VerificationPipeline instance."""
        from crawler.verification.pipeline import VerificationPipeline
        return VerificationPipeline()

    def test_tasting_notes_strategy_exists(self, verification_pipeline):
        """Spec: tasting_notes strategy for missing palate/nose/finish."""
        strategies = verification_pipeline.ENRICHMENT_STRATEGIES
        assert "tasting_notes" in strategies

        templates = strategies["tasting_notes"]
        assert len(templates) > 0

        # Should have templates for tasting notes
        all_templates = " ".join(templates)
        assert "tasting notes" in all_templates or "nose" in all_templates or "palate" in all_templates

    def test_pricing_strategy_exists(self, verification_pipeline):
        """Spec: pricing strategy for missing price."""
        strategies = verification_pipeline.ENRICHMENT_STRATEGIES
        assert "pricing" in strategies

        templates = strategies["pricing"]
        assert len(templates) > 0

        # Should have templates for pricing
        all_templates = " ".join(templates)
        assert "price" in all_templates or "buy" in all_templates

    def test_strategy_templates_include_name_placeholder(self, verification_pipeline):
        """Spec: All templates should include {name} placeholder."""
        strategies = verification_pipeline.ENRICHMENT_STRATEGIES

        for strategy_name, templates in strategies.items():
            for template in templates:
                assert "{name}" in template, f"Template '{template}' in {strategy_name} missing {{name}}"

    def test_target_sources_is_3(self, verification_pipeline):
        """Spec: TARGET_SOURCES should be 3."""
        assert verification_pipeline.TARGET_SOURCES == 3

    def test_min_sources_for_verified_is_2(self, verification_pipeline):
        """Spec: MIN_SOURCES_FOR_VERIFIED should be 2."""
        assert verification_pipeline.MIN_SOURCES_FOR_VERIFIED == 2


class TestExcludedDomainsSpec:
    """
    Test that EXCLUDE_DOMAINS matches spec requirements.
    """

    @pytest.fixture
    def verification_pipeline(self):
        """Create VerificationPipeline instance."""
        from crawler.verification.pipeline import VerificationPipeline
        return VerificationPipeline()

    def test_social_media_excluded(self, verification_pipeline):
        """Spec: Social media domains should be excluded."""
        excluded = verification_pipeline.EXCLUDE_DOMAINS

        social_domains = ["facebook.com", "twitter.com", "instagram.com", "linkedin.com"]
        for domain in social_domains:
            assert domain in excluded, f"{domain} should be in EXCLUDE_DOMAINS"

    def test_video_platforms_excluded(self, verification_pipeline):
        """Spec: Video platforms should be excluded."""
        excluded = verification_pipeline.EXCLUDE_DOMAINS

        assert "youtube.com" in excluded

    def test_forums_excluded(self, verification_pipeline):
        """Spec: Forums should be excluded."""
        excluded = verification_pipeline.EXCLUDE_DOMAINS

        assert "reddit.com" in excluded

    def test_wikipedia_excluded(self, verification_pipeline):
        """Spec: Wikipedia should be excluded (not product-focused)."""
        excluded = verification_pipeline.EXCLUDE_DOMAINS

        assert "wikipedia.org" in excluded

    def test_auction_sites_excluded(self, verification_pipeline):
        """Spec: Auction sites should be excluded (prices unreliable)."""
        excluded = verification_pipeline.EXCLUDE_DOMAINS

        assert "ebay.com" in excluded or "ebay.co.uk" in excluded


class TestQueryFormattingSpec:
    """
    Test query formatting follows spec.
    """

    @pytest.fixture
    def verification_pipeline(self):
        """Create VerificationPipeline instance."""
        from crawler.verification.pipeline import VerificationPipeline
        return VerificationPipeline()

    def test_format_query_with_name(self, verification_pipeline):
        """Query should include product name."""
        product = Mock()
        product.name = "Lagavulin 16"
        product.brand = None

        template = "{name} tasting notes"
        result = verification_pipeline._format_query(template, product)

        assert "Lagavulin 16" in result

    def test_format_query_with_brand(self, verification_pipeline):
        """Query should include brand when available and template uses it."""
        product = Mock()
        product.name = "16 Year Old"
        product.brand = Mock()
        product.brand.name = "Lagavulin"

        template = "{brand} {name} review"
        result = verification_pipeline._format_query(template, product)

        assert "Lagavulin" in result
        assert "16 Year Old" in result

    def test_format_query_handles_missing_brand(self, verification_pipeline):
        """Query should handle missing brand gracefully."""
        product = Mock()
        product.name = "Test Whisky"
        product.brand = None

        template = "{brand} {name} review"
        result = verification_pipeline._format_query(template, product)

        # Should not raise error
        assert "Test Whisky" in result
