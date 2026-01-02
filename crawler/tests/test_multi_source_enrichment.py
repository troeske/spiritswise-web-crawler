"""
Tests for SmartCrawler Multi-Source Enrichment.

Fix 3 of Duplicate Crawling Fixes: Extract from multiple sources and merge
results to enrich product data.

TDD Approach: These tests are written FIRST before implementation.

Tests verify:
1. Extracts from multiple sources (up to max_sources)
2. Merges non-conflicting fields from different sources
3. Detects and reports conflicts between sources
4. Sets needs_review when conflicts exist
5. Works with single source (no merge needed)
6. Returns failure when no sources match expected name
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from crawler.services.smart_crawler import SmartCrawler, ExtractionResult


@pytest.mark.django_db
class TestMultiSourceEnrichment:
    """Tests for SmartCrawler multi-source extraction and merge functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_scrapingbee = Mock()
        self.mock_ai_client = Mock()
        self.crawler = SmartCrawler(
            scrapingbee_client=self.mock_scrapingbee,
            ai_client=self.mock_ai_client
        )

    def test_extracts_from_multiple_sources(self):
        """Should extract from up to 3 sources when available."""
        # Mock SerpAPI to return 3 URLs
        with patch.object(self.crawler, '_search_product') as mock_search:
            mock_search.return_value = [
                "https://source1.com/product",
                "https://source2.com/product",
                "https://source3.com/product",
            ]

            # Mock _try_extraction to return success for all 3
            extraction_results = [
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey 12 Year",
                            "abv": 40.0,
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey 12 Year",
                            "price": 49.99,
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey 12 Year Old",
                            "region": "Speyside",
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results) as mock_extract:
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey 12 Year",
                    product_type="whiskey",
                    max_sources=3,
                )

                # Verify all 3 extractions were tried
                assert mock_extract.call_count == 3
                assert result.success is True

    def test_merges_non_conflicting_fields(self):
        """Should merge fields that don't conflict."""
        with patch.object(self.crawler, '_search_product') as mock_search:
            mock_search.return_value = [
                "https://source1.com/product",
                "https://source2.com/product",
            ]

            # Source 1: has ABV, tasting notes
            # Source 2: has price, images
            extraction_results = [
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "abv": 40.0,
                            "nose_description": "Honey and vanilla",
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "price": 49.99,
                            "images": ["https://example.com/img1.jpg"],
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results):
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey",
                    product_type="whiskey",
                    max_sources=3,
                )

                # Merged result should have all fields
                extracted = result.data.get("extracted_data", {})
                assert extracted.get("abv") == 40.0
                assert extracted.get("nose_description") == "Honey and vanilla"
                assert extracted.get("price") == 49.99
                assert "images" in extracted
                assert result.success is True

    def test_detects_conflicts(self):
        """Should detect and report conflicting values."""
        with patch.object(self.crawler, '_search_product') as mock_search:
            mock_search.return_value = [
                "https://source1.com/product",
                "https://source2.com/product",
            ]

            # Source 1: ABV = 40%
            # Source 2: ABV = 43%
            extraction_results = [
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "abv": 40.0,
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "abv": 43.0,
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results):
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey",
                    product_type="whiskey",
                    max_sources=3,
                )

                # Should flag conflict
                assert result.success is True
                assert len(result.conflicts) > 0
                conflict_fields = [c["field"] for c in result.conflicts]
                assert "abv" in conflict_fields

    def test_flags_conflicts_for_review(self):
        """Should set needs_review when conflicts exist."""
        with patch.object(self.crawler, '_search_product') as mock_search:
            mock_search.return_value = [
                "https://source1.com/product",
                "https://source2.com/product",
            ]

            # Create conflicting extractions
            extraction_results = [
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "abv": 40.0,
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "abv": 43.0,
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results):
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey",
                    product_type="whiskey",
                    max_sources=3,
                )

                # Verify needs_review = True
                assert result.needs_review is True
                assert any("Conflict" in reason for reason in result.review_reasons)

    def test_uses_single_source_when_only_one_available(self):
        """Should work with single source (no merge needed)."""
        with patch.object(self.crawler, '_search_product') as mock_search:
            # Only 1 URL found
            mock_search.return_value = [
                "https://source1.com/product",
            ]

            extraction_results = [
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "abv": 40.0,
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results):
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey",
                    product_type="whiskey",
                    max_sources=3,
                )

                # Should return that extraction directly
                assert result.success is True
                assert result.data["extracted_data"]["abv"] == 40.0
                assert result.sources_used == 1

    def test_returns_failure_when_no_sources_match(self):
        """Should return failure when no sources match expected name."""
        with patch.object(self.crawler, '_search_product') as mock_search:
            mock_search.return_value = [
                "https://source1.com/product",
                "https://source2.com/product",
            ]

            # All extractions fail name match
            extraction_results = [
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Completely Different Product",
                            "abv": 40.0,
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Another Wrong Product",
                            "abv": 43.0,
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results):
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey",
                    product_type="whiskey",
                    max_sources=3,
                    name_match_threshold=0.6,
                )

                # Should return success=False
                assert result.success is False
                assert len(result.errors) > 0

    def test_stops_after_max_sources(self):
        """Should stop after reaching max_sources successful extractions."""
        with patch.object(self.crawler, '_search_product') as mock_search:
            mock_search.return_value = [
                "https://source1.com/product",
                "https://source2.com/product",
                "https://source3.com/product",
                "https://source4.com/product",
                "https://source5.com/product",
            ]

            extraction_results = [
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "abv": 40.0,
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "price": 49.99,
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "region": "Speyside",
                        }
                    }
                },
                # These should not be reached
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results) as mock_extract:
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey",
                    product_type="whiskey",
                    max_sources=3,
                )

                # Should stop at 3 successful extractions
                assert mock_extract.call_count == 3
                assert result.sources_used == 3

    def test_merges_list_fields_without_duplicates(self):
        """Should combine list fields (awards, images) without duplicates."""
        with patch.object(self.crawler, '_search_product') as mock_search:
            mock_search.return_value = [
                "https://source1.com/product",
                "https://source2.com/product",
            ]

            extraction_results = [
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "images": ["https://img1.com/a.jpg", "https://img2.com/b.jpg"],
                            "awards": [
                                {"competition": "IWSC", "year": 2024, "medal": "Gold"}
                            ],
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "images": ["https://img2.com/b.jpg", "https://img3.com/c.jpg"],  # One duplicate
                            "awards": [
                                {"competition": "SWA", "year": 2024, "medal": "Silver"}
                            ],
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results):
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey",
                    product_type="whiskey",
                    max_sources=3,
                )

                extracted = result.data.get("extracted_data", {})

                # Should have 3 unique images (one duplicate removed)
                assert len(extracted.get("images", [])) == 3

                # Should have 2 awards combined
                assert len(extracted.get("awards", [])) == 2

    def test_skips_failed_extractions(self):
        """Should skip failed extractions and continue trying."""
        with patch.object(self.crawler, '_search_product') as mock_search:
            mock_search.return_value = [
                "https://source1.com/product",
                "https://source2.com/product",
                "https://source3.com/product",
            ]

            extraction_results = [
                {
                    "success": False,
                    "error": "Crawl failed",
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "abv": 40.0,
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "price": 49.99,
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results) as mock_extract:
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey",
                    product_type="whiskey",
                    max_sources=3,
                )

                # All 3 should be tried (first failed)
                assert mock_extract.call_count == 3
                # Only 2 successful
                assert result.success is True
                assert result.sources_used == 2

    def test_uses_primary_url_first(self):
        """Should try primary URL before SerpAPI results."""
        with patch.object(self.crawler, '_search_product') as mock_search:
            mock_search.return_value = [
                "https://serpapi1.com/product",
                "https://serpapi2.com/product",
            ]

            extraction_results = [
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "abv": 40.0,
                        }
                    }
                },
                {
                    "success": True,
                    "data": {
                        "extracted_data": {
                            "name": "Test Whiskey",
                            "price": 49.99,
                        }
                    }
                },
            ]

            with patch.object(self.crawler, '_try_extraction', side_effect=extraction_results) as mock_extract:
                result = self.crawler.extract_product_multi_source(
                    expected_name="Test Whiskey",
                    product_type="whiskey",
                    primary_url="https://primary.com/product",
                    max_sources=2,
                )

                # First call should be primary URL
                first_call_url = mock_extract.call_args_list[0][0][0]
                assert first_call_url == "https://primary.com/product"


@pytest.mark.django_db
class TestMergeExtractions:
    """Tests for the _merge_extractions helper method."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_scrapingbee = Mock()
        self.mock_ai_client = Mock()
        self.crawler = SmartCrawler(
            scrapingbee_client=self.mock_scrapingbee,
            ai_client=self.mock_ai_client
        )

    def test_merge_empty_extractions(self):
        """Should handle empty extraction list."""
        result = self.crawler._merge_extractions([])

        assert result["data"] == {}
        assert result["has_conflicts"] is False
        assert result["conflicts"] == []

    def test_merge_single_extraction(self):
        """Should return single extraction data unchanged."""
        extractions = [
            {
                "url": "https://source1.com/product",
                "data": {
                    "extracted_data": {
                        "name": "Test Whiskey",
                        "abv": 40.0,
                    }
                },
                "match_score": 0.95,
            }
        ]

        result = self.crawler._merge_extractions(extractions)

        assert result["data"]["extracted_data"]["name"] == "Test Whiskey"
        assert result["data"]["extracted_data"]["abv"] == 40.0
        assert result["has_conflicts"] is False

    def test_merge_uses_first_value_for_scalar_fields(self):
        """Should use first non-empty value for scalar fields."""
        extractions = [
            {
                "url": "https://source1.com",
                "data": {
                    "extracted_data": {
                        "name": "Test Whiskey",
                        "abv": 40.0,
                    }
                },
            },
            {
                "url": "https://source2.com",
                "data": {
                    "extracted_data": {
                        "name": "Test Whiskey - Different",
                        "abv": 43.0,
                        "price": 59.99,
                    }
                },
            },
        ]

        result = self.crawler._merge_extractions(extractions)

        # Should use first source's values
        assert result["data"]["extracted_data"]["abv"] == 40.0
        # But should include fields only in second source
        assert result["data"]["extracted_data"]["price"] == 59.99

    def test_merge_reports_conflicts_for_different_values(self):
        """Should report conflicts when same field has different values."""
        extractions = [
            {
                "url": "https://source1.com",
                "data": {
                    "extracted_data": {
                        "name": "Test Whiskey",
                        "abv": 40.0,
                    }
                },
            },
            {
                "url": "https://source2.com",
                "data": {
                    "extracted_data": {
                        "name": "Test Whiskey",
                        "abv": 43.0,
                    }
                },
            },
        ]

        result = self.crawler._merge_extractions(extractions)

        assert result["has_conflicts"] is True
        assert len(result["conflicts"]) == 1
        assert result["conflicts"][0]["field"] == "abv"

    def test_merge_combines_list_fields(self):
        """Should combine list fields from all sources."""
        extractions = [
            {
                "url": "https://source1.com",
                "data": {
                    "extracted_data": {
                        "name": "Test Whiskey",
                        "primary_aromas": ["vanilla", "honey"],
                    }
                },
            },
            {
                "url": "https://source2.com",
                "data": {
                    "extracted_data": {
                        "name": "Test Whiskey",
                        "primary_aromas": ["oak", "caramel"],
                    }
                },
            },
        ]

        result = self.crawler._merge_extractions(extractions)

        aromas = result["data"]["extracted_data"]["primary_aromas"]
        assert len(aromas) == 4
        assert "vanilla" in aromas
        assert "oak" in aromas

    def test_merge_deduplicates_list_items(self):
        """Should remove duplicate items from list fields."""
        extractions = [
            {
                "url": "https://source1.com",
                "data": {
                    "extracted_data": {
                        "name": "Test Whiskey",
                        "images": ["img1.jpg", "img2.jpg"],
                    }
                },
            },
            {
                "url": "https://source2.com",
                "data": {
                    "extracted_data": {
                        "name": "Test Whiskey",
                        "images": ["img2.jpg", "img3.jpg"],  # img2 is duplicate
                    }
                },
            },
        ]

        result = self.crawler._merge_extractions(extractions)

        images = result["data"]["extracted_data"]["images"]
        assert len(images) == 3
        assert images.count("img2.jpg") == 1

    def test_merge_tracks_sources_used(self):
        """Should track number of sources merged."""
        extractions = [
            {
                "url": "https://source1.com",
                "data": {"extracted_data": {"name": "Test"}},
            },
            {
                "url": "https://source2.com",
                "data": {"extracted_data": {"name": "Test"}},
            },
            {
                "url": "https://source3.com",
                "data": {"extracted_data": {"name": "Test"}},
            },
        ]

        result = self.crawler._merge_extractions(extractions)

        assert result["sources_used"] == 3


@pytest.mark.django_db
class TestExtractionResultFields:
    """Tests for ExtractionResult dataclass new fields."""

    def test_extraction_result_has_sources_used_field(self):
        """ExtractionResult should have sources_used field."""
        result = ExtractionResult(success=True)

        assert hasattr(result, 'sources_used')
        assert result.sources_used == 1  # default

    def test_extraction_result_has_conflicts_field(self):
        """ExtractionResult should have conflicts field."""
        result = ExtractionResult(success=True)

        assert hasattr(result, 'conflicts')
        assert result.conflicts == []  # default empty list

    def test_extraction_result_can_store_conflicts(self):
        """ExtractionResult should be able to store conflict details."""
        result = ExtractionResult(
            success=True,
            conflicts=[
                {"field": "abv", "values": [{"source": "url1", "value": 40}, {"source": "url2", "value": 43}]}
            ]
        )

        assert len(result.conflicts) == 1
        assert result.conflicts[0]["field"] == "abv"
