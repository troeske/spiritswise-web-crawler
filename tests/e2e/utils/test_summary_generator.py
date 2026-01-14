"""
Test: Summary Generator Validation - Task 6.1.

Tests the SummaryGenerator class for comprehensive report generation:
1. Aggregate all test results
2. Calculate overall metrics
3. Generate Markdown summary
4. Generate JSON summary
5. Include analysis and recommendations

Spec Reference: E2E_DOMAIN_INTELLIGENCE_TEST_SUITE.md - Task 6.1
"""

import json
import pytest
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from tests.e2e.utils.results_exporter import ResultsExporter, SummaryGenerator


class TestSummaryGenerator:
    """
    Tests for SummaryGenerator class.

    Validates comprehensive report generation from E2E test results.
    """

    @pytest.fixture
    def sample_results(self) -> Dict[str, Any]:
        """Create sample test results for summary generation."""
        return {
            "test_name": "full_pipeline_e2e",
            "started_at": "2026-01-14T10:00:00Z",
            "completed_at": "2026-01-14T10:30:00Z",
            "status": "COMPLETED",
            "products": [
                {
                    "id": "prod-001",
                    "name": "Ardbeg 10 Year Old",
                    "brand": "Ardbeg",
                    "product_type": "whiskey",
                    "status": "BASELINE",
                    "ecp_score": 75.5,
                    "flow": "single_product",
                    "sources_used": [
                        {
                            "url": "https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/",
                            "source_type": "product_page",
                            "tier_used": 3,
                            "domain": "masterofmalt.com",
                        }
                    ],
                    "domain_intelligence": {
                        "primary_domain": "masterofmalt.com",
                        "tier_used": 3,
                    },
                    "field_values": {
                        "abv": 46.0,
                        "description": "A heavily peated Islay single malt with complex smoky flavors.",
                        "distillery": "Ardbeg Distillery",
                        "region": "Islay",
                        "age_statement": 10,
                    },
                },
                {
                    "id": "prod-002",
                    "name": "Taylor Fladgate 10 Year Tawny Port",
                    "brand": "Taylor Fladgate",
                    "product_type": "port_wine",
                    "status": "ENRICHED",
                    "ecp_score": 82.3,
                    "flow": "competition",
                    "sources_used": [
                        {
                            "url": "https://www.wine-searcher.com/find/taylor+fladgate+10+yr+old+tawny+port",
                            "source_type": "product_page",
                            "tier_used": 1,
                            "domain": "wine-searcher.com",
                        },
                        {
                            "url": "https://www.iwsc.net/results/search/2024?q=taylor",
                            "source_type": "competition",
                            "tier_used": 2,
                            "domain": "iwsc.net",
                        },
                    ],
                    "domain_intelligence": {
                        "primary_domain": "wine-searcher.com",
                        "tier_used": 1,
                    },
                    "field_values": {
                        "abv": 20.0,
                        "description": "A rich tawny port with nutty, caramel notes.",
                        "style": "Tawny",
                        "vintage": None,
                        "producer_house": "Taylor Fladgate",
                    },
                },
                {
                    "id": "prod-003",
                    "name": "Buffalo Trace Bourbon",
                    "brand": "Buffalo Trace",
                    "product_type": "whiskey",
                    "status": "SKELETON",
                    "ecp_score": 45.0,
                    "flow": "generic_search",
                    "sources_used": [
                        {
                            "url": "https://example.com/bourbon-list",
                            "source_type": "listicle",
                            "tier_used": 1,
                            "domain": "example.com",
                        },
                    ],
                    "domain_intelligence": {
                        "primary_domain": "example.com",
                        "tier_used": 1,
                    },
                    "field_values": {
                        "abv": 40.0,
                    },
                },
            ],
            "domain_profiles": [
                {
                    "domain": "masterofmalt.com",
                    "likely_js_heavy": False,
                    "likely_bot_protected": True,
                    "likely_slow": False,
                    "recommended_tier": 3,
                },
                {
                    "domain": "wine-searcher.com",
                    "likely_js_heavy": False,
                    "likely_bot_protected": False,
                    "likely_slow": False,
                    "recommended_tier": 1,
                },
                {
                    "domain": "iwsc.net",
                    "likely_js_heavy": True,
                    "likely_bot_protected": False,
                    "likely_slow": False,
                    "recommended_tier": 2,
                },
                {
                    "domain": "vivino.com",
                    "likely_js_heavy": True,
                    "likely_bot_protected": False,
                    "likely_slow": True,
                    "recommended_tier": 2,
                },
            ],
            "metrics": {
                "total_products": 3,
                "products_by_status": {
                    "BASELINE": 1,
                    "ENRICHED": 1,
                    "SKELETON": 1,
                },
                "products_by_flow": {
                    "single_product": 1,
                    "competition": 1,
                    "generic_search": 1,
                },
                "baseline_achieved": 2,
                "average_ecp": 67.6,
                "tier_distribution": {
                    "tier_1": 2,
                    "tier_2": 1,
                    "tier_3": 1,
                },
                "sources_per_product_avg": 1.33,
                "cross_contamination_count": 0,
            },
            "errors": [],
        }

    def test_markdown_summary_generation(self, sample_results: Dict[str, Any]):
        """Test that Markdown summary is generated correctly."""
        generator = SummaryGenerator(sample_results)
        markdown = generator.generate_markdown_summary()

        # Verify header
        assert "# E2E Test Results Summary" in markdown
        assert "**Test:** full_pipeline_e2e" in markdown
        assert "**Status:** COMPLETED" in markdown

        # Verify executive summary
        assert "## Executive Summary" in markdown
        assert "**Total Products:** 3" in markdown
        assert "**Baseline Achieved:** 2" in markdown

        # Verify status distribution table
        assert "### Status Distribution" in markdown
        assert "| BASELINE | 1 |" in markdown
        assert "| ENRICHED | 1 |" in markdown
        assert "| SKELETON | 1 |" in markdown

        # Verify flow distribution table
        assert "### Flow Distribution" in markdown
        assert "single_product" in markdown
        assert "competition" in markdown
        assert "generic_search" in markdown

        # Verify tier usage table
        assert "### Tier Usage" in markdown
        assert "Tier 1" in markdown or "tier_1" in markdown

        # Verify domain intelligence section
        assert "## Domain Intelligence Analysis" in markdown
        assert "**JS-Heavy Domains:**" in markdown
        assert "iwsc.net" in markdown
        assert "vivino.com" in markdown
        assert "**Bot-Protected Domains:**" in markdown
        assert "masterofmalt.com" in markdown

        # Verify product details
        assert "## Product Details" in markdown
        assert "Ardbeg 10 Year Old" in markdown
        assert "Taylor Fladgate 10 Year Tawny Port" in markdown
        assert "Buffalo Trace Bourbon" in markdown

    def test_json_summary_generation(self, sample_results: Dict[str, Any]):
        """Test that JSON summary is generated correctly."""
        generator = SummaryGenerator(sample_results)
        json_summary = generator.generate_json_summary()

        # Verify structure
        assert json_summary["test_name"] == "full_pipeline_e2e"
        assert json_summary["status"] == "COMPLETED"
        assert json_summary["domain_profiles_count"] == 4
        assert json_summary["errors_count"] == 0

        # Verify metrics
        metrics = json_summary["metrics"]
        assert metrics["total_products"] == 3
        assert metrics["baseline_achieved"] == 2

        # Verify products summary
        products = json_summary["products_summary"]
        assert len(products) == 3
        assert products[0]["name"] == "Ardbeg 10 Year Old"
        assert products[0]["sources_count"] == 1
        assert products[1]["sources_count"] == 2

    def test_empty_results_handling(self):
        """Test handling of empty results."""
        empty_results = {
            "test_name": "empty_test",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "status": "COMPLETED",
            "products": [],
            "domain_profiles": [],
            "metrics": {
                "total_products": 0,
                "products_by_status": {},
                "products_by_flow": {},
                "baseline_achieved": 0,
                "average_ecp": 0.0,
                "tier_distribution": {"tier_1": 0, "tier_2": 0, "tier_3": 0},
            },
            "errors": [],
        }

        generator = SummaryGenerator(empty_results)

        # Markdown should still generate
        markdown = generator.generate_markdown_summary()
        assert "# E2E Test Results Summary" in markdown
        assert "**Total Products:** 0" in markdown

        # JSON should still generate
        json_summary = generator.generate_json_summary()
        assert json_summary["metrics"]["total_products"] == 0
        assert len(json_summary["products_summary"]) == 0

    def test_error_reporting_in_summary(self):
        """Test that errors are properly included in summary."""
        results_with_errors = {
            "test_name": "error_test",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "status": "PARTIAL",
            "products": [],
            "domain_profiles": [],
            "metrics": {
                "total_products": 0,
                "products_by_status": {},
                "products_by_flow": {},
                "baseline_achieved": 0,
                "average_ecp": 0.0,
                "tier_distribution": {"tier_1": 0, "tier_2": 0, "tier_3": 0},
            },
            "errors": [
                {
                    "timestamp": "2026-01-14T10:15:00Z",
                    "message": "Failed to fetch masterofmalt.com: Cloudflare challenge",
                    "step": "fetch_url_1",
                },
                {
                    "timestamp": "2026-01-14T10:20:00Z",
                    "message": "AI extraction timeout",
                    "step": "extract_products",
                },
            ],
        }

        generator = SummaryGenerator(results_with_errors)
        markdown = generator.generate_markdown_summary()

        # Verify errors section exists
        assert "## Errors" in markdown
        assert "Cloudflare challenge" in markdown
        assert "AI extraction timeout" in markdown

        # JSON should report error count
        json_summary = generator.generate_json_summary()
        assert json_summary["errors_count"] == 2

    def test_product_details_truncation(self):
        """Test that product details are truncated for readability."""
        many_products = {
            "test_name": "many_products_test",
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat(),
            "status": "COMPLETED",
            "products": [
                {
                    "id": f"prod-{i:03d}",
                    "name": f"Product {i}",
                    "brand": f"Brand {i}",
                    "product_type": "whiskey",
                    "status": "SKELETON",
                    "ecp_score": 50.0,
                    "flow": "generic_search",
                    "sources_used": [],
                }
                for i in range(30)
            ],
            "domain_profiles": [],
            "metrics": {
                "total_products": 30,
                "products_by_status": {"SKELETON": 30},
                "products_by_flow": {"generic_search": 30},
                "baseline_achieved": 0,
                "average_ecp": 50.0,
                "tier_distribution": {"tier_1": 30, "tier_2": 0, "tier_3": 0},
            },
            "errors": [],
        }

        generator = SummaryGenerator(many_products)
        markdown = generator.generate_markdown_summary()

        # Should only show first 20 products in detail
        assert "### 1. Product 0" in markdown
        assert "### 20. Product 19" in markdown
        # Product 21 (index 20) should not be in detail
        assert "### 21." not in markdown
        # Should mention remaining products
        assert "and 10 more products" in markdown

    def test_results_exporter_integration(self, tmp_path):
        """Test ResultsExporter integrates with SummaryGenerator."""
        # Create exporter
        exporter = ResultsExporter("integration_test")

        # Add products
        exporter.add_product({
            "id": "test-001",
            "name": "Test Whiskey",
            "brand": "Test Brand",
            "product_type": "whiskey",
            "status": "BASELINE",
            "ecp_score": 70.0,
            "flow": "single_product",
        })

        exporter.add_domain_profile({
            "domain": "test.com",
            "likely_js_heavy": False,
            "likely_bot_protected": False,
        })

        exporter.set_metrics({
            "total_products": 1,
            "baseline_achieved": 1,
        })

        # Finalize
        exporter.finalize("COMPLETED")

        # Get results and generate summary
        results = exporter.get_results()
        generator = SummaryGenerator(results)

        markdown = generator.generate_markdown_summary()
        assert "Test Whiskey" in markdown
        assert "**Status:** COMPLETED" in markdown

        json_summary = generator.generate_json_summary()
        assert json_summary["metrics"]["total_products"] == 1


class TestAggregatedSummaryGeneration:
    """
    Tests for aggregating multiple test results into a single summary.
    """

    @pytest.fixture
    def multi_test_results(self) -> List[Dict[str, Any]]:
        """Create results from multiple tests for aggregation."""
        return [
            {
                "test_name": "iwsc_competition_e2e",
                "status": "COMPLETED",
                "products": [
                    {"id": "p1", "name": "IWSC Gold Winner", "status": "ENRICHED"},
                ],
                "metrics": {
                    "total_products": 5,
                    "baseline_achieved": 4,
                    "tier_distribution": {"tier_1": 0, "tier_2": 5, "tier_3": 0},
                },
                "domain_profiles": [
                    {"domain": "iwsc.net", "likely_js_heavy": True},
                ],
                "errors": [],
            },
            {
                "test_name": "single_product_whiskey_e2e",
                "status": "COMPLETED",
                "products": [
                    {"id": "p2", "name": "Ardbeg 10", "status": "BASELINE"},
                    {"id": "p3", "name": "Glenfiddich 18", "status": "SKELETON"},
                ],
                "metrics": {
                    "total_products": 3,
                    "baseline_achieved": 2,
                    "tier_distribution": {"tier_1": 1, "tier_2": 1, "tier_3": 1},
                },
                "domain_profiles": [
                    {"domain": "masterofmalt.com", "likely_bot_protected": True},
                ],
                "errors": [
                    {"message": "Timeout on masterofmalt.com"},
                ],
            },
        ]

    def test_aggregate_multiple_results(self, multi_test_results: List[Dict[str, Any]]):
        """Test aggregating multiple test results."""
        # Aggregate results
        aggregated = {
            "test_name": "aggregated_e2e_summary",
            "started_at": "2026-01-14T10:00:00Z",
            "completed_at": "2026-01-14T12:00:00Z",
            "status": "COMPLETED",
            "products": [],
            "domain_profiles": [],
            "metrics": {
                "total_products": 0,
                "products_by_status": {},
                "products_by_flow": {},
                "baseline_achieved": 0,
                "average_ecp": 0.0,
                "tier_distribution": {"tier_1": 0, "tier_2": 0, "tier_3": 0},
            },
            "errors": [],
            "sub_tests": [],
        }

        for result in multi_test_results:
            # Aggregate products
            aggregated["products"].extend(result.get("products", []))

            # Aggregate domain profiles (dedupe by domain)
            for profile in result.get("domain_profiles", []):
                if not any(p["domain"] == profile["domain"] for p in aggregated["domain_profiles"]):
                    aggregated["domain_profiles"].append(profile)

            # Aggregate metrics
            aggregated["metrics"]["total_products"] += result["metrics"]["total_products"]
            aggregated["metrics"]["baseline_achieved"] += result["metrics"]["baseline_achieved"]

            for tier, count in result["metrics"]["tier_distribution"].items():
                aggregated["metrics"]["tier_distribution"][tier] += count

            # Aggregate errors
            aggregated["errors"].extend(result.get("errors", []))

            # Track sub-tests
            aggregated["sub_tests"].append({
                "name": result["test_name"],
                "status": result["status"],
                "products_count": result["metrics"]["total_products"],
            })

        # Generate summary from aggregated results
        generator = SummaryGenerator(aggregated)
        markdown = generator.generate_markdown_summary()

        # Verify aggregated totals
        assert "**Total Products:** 8" in markdown  # 5 + 3
        assert "**Baseline Achieved:** 6" in markdown  # 4 + 2

        # Verify both domain profiles are included
        assert len(aggregated["domain_profiles"]) == 2
        assert "iwsc.net" in markdown
        assert "masterofmalt.com" in markdown

        # Verify errors from all tests
        assert len(aggregated["errors"]) == 1


class TestSummaryFileOutput:
    """
    Tests for saving summary reports to files.
    """

    def test_save_markdown_summary(self, tmp_path, sample_results=None):
        """Test saving Markdown summary to file."""
        if sample_results is None:
            sample_results = {
                "test_name": "save_test",
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "status": "COMPLETED",
                "products": [{"name": "Test Product", "status": "BASELINE"}],
                "domain_profiles": [],
                "metrics": {
                    "total_products": 1,
                    "products_by_status": {"BASELINE": 1},
                    "products_by_flow": {},
                    "baseline_achieved": 1,
                    "average_ecp": 75.0,
                    "tier_distribution": {"tier_1": 1, "tier_2": 0, "tier_3": 0},
                },
                "errors": [],
            }

        generator = SummaryGenerator(sample_results)
        markdown = generator.generate_markdown_summary()

        # Save to file
        output_path = tmp_path / "summary.md"
        output_path.write_text(markdown, encoding="utf-8")

        # Verify file was created and contains content
        assert output_path.exists()
        content = output_path.read_text(encoding="utf-8")
        assert "# E2E Test Results Summary" in content

    def test_save_json_summary(self, tmp_path, sample_results=None):
        """Test saving JSON summary to file."""
        if sample_results is None:
            sample_results = {
                "test_name": "json_save_test",
                "started_at": datetime.utcnow().isoformat(),
                "completed_at": datetime.utcnow().isoformat(),
                "status": "COMPLETED",
                "products": [],
                "domain_profiles": [],
                "metrics": {
                    "total_products": 0,
                    "products_by_status": {},
                    "products_by_flow": {},
                    "baseline_achieved": 0,
                    "average_ecp": 0.0,
                    "tier_distribution": {"tier_1": 0, "tier_2": 0, "tier_3": 0},
                },
                "errors": [],
            }

        generator = SummaryGenerator(sample_results)
        json_summary = generator.generate_json_summary()

        # Save to file
        output_path = tmp_path / "summary.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(json_summary, f, indent=2)

        # Verify file was created and is valid JSON
        assert output_path.exists()
        with open(output_path, "r", encoding="utf-8") as f:
            loaded = json.load(f)
        assert loaded["test_name"] == "json_save_test"


@pytest.fixture
def sample_results() -> Dict[str, Any]:
    """Create sample test results for summary generation."""
    return {
        "test_name": "fixture_test",
        "started_at": "2026-01-14T10:00:00Z",
        "completed_at": "2026-01-14T10:30:00Z",
        "status": "COMPLETED",
        "products": [],
        "domain_profiles": [],
        "metrics": {
            "total_products": 0,
            "products_by_status": {},
            "products_by_flow": {},
            "baseline_achieved": 0,
            "average_ecp": 0.0,
            "tier_distribution": {"tier_1": 0, "tier_2": 0, "tier_3": 0},
        },
        "errors": [],
    }
