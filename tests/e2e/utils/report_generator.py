"""
Markdown Report Generator for E2E Tests.

Generates comprehensive E2E test reports in Markdown format.
Reports are saved to specs/E2E_TEST_RESULTS_V2.md.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# Report output location
REPORT_OUTPUT_PATH = "specs/E2E_TEST_RESULTS_V2.md"


class ReportGenerator:
    """
    Generates Markdown reports for E2E test results.

    Features:
    - Summary statistics
    - Product details table
    - Source tracking summary
    - Verification checklist results
    - Flow execution details
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize the report generator.

        Args:
            base_path: Base path for the project (defaults to current working directory)
        """
        self.base_path = base_path or os.getcwd()
        self.report_path = os.path.join(self.base_path, REPORT_OUTPUT_PATH)

    def generate_report(
        self,
        test_run_id: str,
        start_time: datetime,
        end_time: Optional[datetime],
        products: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        awards: List[Dict[str, Any]],
        flow_results: Dict[str, Dict[str, Any]],
        verification_results: Dict[str, bool],
        api_calls: Dict[str, int],
        errors: List[Dict[str, Any]],
    ) -> str:
        """
        Generate the complete E2E test report.

        Args:
            test_run_id: Unique identifier for the test run
            start_time: When the test run started
            end_time: When the test run completed
            products: List of product data dictionaries
            sources: List of source data dictionaries
            awards: List of award data dictionaries
            flow_results: Results from each flow execution
            verification_results: Pass/fail for each verification check
            api_calls: Count of API calls per service
            errors: List of errors encountered

        Returns:
            The generated Markdown report as a string
        """
        duration = None
        if end_time:
            duration = (end_time - start_time).total_seconds()

        sections = [
            self._generate_header(test_run_id, start_time, end_time, duration),
            self._generate_summary_statistics(products, sources, awards, api_calls),
            self._generate_flow_results(flow_results),
            self._generate_product_details(products),
            self._generate_source_tracking_summary(sources, products),
            self._generate_verification_checklist(verification_results),
            self._generate_errors_section(errors),
            self._generate_footer(),
        ]

        report = "\n\n".join(sections)
        return report

    def save_report(self, report_content: str) -> str:
        """
        Save the report to the output file.

        Args:
            report_content: The Markdown report content

        Returns:
            The path where the report was saved
        """
        # Ensure directory exists
        report_dir = os.path.dirname(self.report_path)
        if report_dir:
            os.makedirs(report_dir, exist_ok=True)

        with open(self.report_path, "w", encoding="utf-8") as f:
            f.write(report_content)

        return self.report_path

    def _generate_header(
        self,
        test_run_id: str,
        start_time: datetime,
        end_time: Optional[datetime],
        duration: Optional[float],
    ) -> str:
        """Generate the report header section."""
        end_str = end_time.strftime("%Y-%m-%d %H:%M:%S") if end_time else "In Progress"
        duration_str = f"{duration:.1f} seconds" if duration else "N/A"

        return f"""# E2E Test Results - V2 Architecture

**Test Run ID**: `{test_run_id}`
**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## Execution Details

| Metric | Value |
|--------|-------|
| Start Time | {start_time.strftime("%Y-%m-%d %H:%M:%S")} |
| End Time | {end_str} |
| Duration | {duration_str} |"""

    def _generate_summary_statistics(
        self,
        products: List[Dict[str, Any]],
        sources: List[Dict[str, Any]],
        awards: List[Dict[str, Any]],
        api_calls: Dict[str, int],
    ) -> str:
        """Generate the summary statistics section."""
        # Count products by type
        whiskey_count = sum(1 for p in products if p.get("product_type") == "whiskey")
        port_wine_count = sum(1 for p in products if p.get("product_type") == "port_wine")

        # Count products by status
        status_counts: Dict[str, int] = {}
        for product in products:
            status = product.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

        # Count awards by competition
        award_counts: Dict[str, int] = {}
        for award in awards:
            competition = award.get("competition", "unknown")
            award_counts[competition] = award_counts.get(competition, 0) + 1

        # Products with palate_flavors
        with_palate = sum(1 for p in products if p.get("palate_flavors"))

        status_rows = "\n".join(
            f"| {status.title()} | {count} |"
            for status, count in sorted(status_counts.items())
        )

        award_rows = "\n".join(
            f"| {comp} | {count} |"
            for comp, count in sorted(award_counts.items())
        )

        return f"""---

## Summary Statistics

### Products Created

| Metric | Count |
|--------|-------|
| **Total Products** | {len(products)} |
| Whiskey Products | {whiskey_count} |
| Port Wine Products | {port_wine_count} |
| Products with Palate Flavors | {with_palate} |

### Product Status Distribution

| Status | Count |
|--------|-------|
{status_rows}

### Awards Recorded

| Competition | Awards |
|-------------|--------|
{award_rows}
| **Total Awards** | {len(awards)} |

### Sources Crawled

| Metric | Count |
|--------|-------|
| Total CrawledSource Records | {len(sources)} |
| Competition Sources | {sum(1 for s in sources if s.get("source_type") == "award_page")} |
| Enrichment Sources | {sum(1 for s in sources if s.get("source_type") != "award_page")} |

### API Calls

| Service | Calls |
|---------|-------|
| OpenAI (via AI Service) | {api_calls.get("openai", 0)} |
| SerpAPI | {api_calls.get("serpapi", 0)} |
| ScrapingBee | {api_calls.get("scrapingbee", 0)} |
| Wayback Machine | {api_calls.get("wayback", 0)} |"""

    def _generate_flow_results(self, flow_results: Dict[str, Dict[str, Any]]) -> str:
        """Generate the flow results section."""
        if not flow_results:
            return """---

## Flow Execution Results

*No flows executed*"""

        rows = []
        for flow_name, result in flow_results.items():
            status = "PASS" if result.get("success") else "FAIL"
            products = result.get("products_created", 0)
            duration = result.get("duration_seconds", 0)
            rows.append(f"| {flow_name} | {status} | {products} | {duration:.1f}s |")

        flow_rows = "\n".join(rows)

        return f"""---

## Flow Execution Results

| Flow | Status | Products Created | Duration |
|------|--------|------------------|----------|
{flow_rows}"""

    def _generate_product_details(self, products: List[Dict[str, Any]]) -> str:
        """Generate the product details table section."""
        if not products:
            return """---

## Product Details

*No products created*"""

        rows = []
        for i, product in enumerate(products, 1):
            name = product.get("name", "Unknown")[:40]
            brand = product.get("brand", "N/A")[:20]
            abv = product.get("abv", "N/A")
            status = product.get("status", "N/A")
            ptype = product.get("product_type", "N/A")
            has_palate = "Yes" if product.get("palate_flavors") else "No"

            rows.append(f"| {i} | {name} | {brand} | {abv} | {status} | {ptype} | {has_palate} |")

        product_rows = "\n".join(rows)

        return f"""---

## Product Details

| # | Name | Brand | ABV | Status | Type | Palate Flavors |
|---|------|-------|-----|--------|------|----------------|
{product_rows}"""

    def _generate_source_tracking_summary(
        self,
        sources: List[Dict[str, Any]],
        products: List[Dict[str, Any]],
    ) -> str:
        """Generate the source tracking summary section."""
        # Count sources per product
        product_source_counts: Dict[str, int] = {}
        for source in sources:
            product_id = source.get("product_id")
            if product_id:
                product_source_counts[product_id] = product_source_counts.get(product_id, 0) + 1

        # Wayback status
        wayback_saved = sum(1 for s in sources if s.get("wayback_status") == "saved")
        wayback_pending = sum(1 for s in sources if s.get("wayback_status") == "pending")
        wayback_failed = sum(1 for s in sources if s.get("wayback_status") == "failed")

        # Products with multiple sources (enriched)
        multi_source_products = sum(1 for count in product_source_counts.values() if count >= 2)

        return f"""---

## Source Tracking Summary

### Source Coverage

| Metric | Value |
|--------|-------|
| Products with >= 1 Source | {len(product_source_counts)} |
| Products with >= 2 Sources (Enriched) | {multi_source_products} |
| Average Sources per Product | {sum(product_source_counts.values()) / max(len(product_source_counts), 1):.1f} |

### Wayback Machine Status

| Status | Count |
|--------|-------|
| Saved | {wayback_saved} |
| Pending | {wayback_pending} |
| Failed | {wayback_failed} |
| **Total** | {len(sources)} |

### Source Types

| Type | Count |
|------|-------|
| Award Page | {sum(1 for s in sources if s.get("source_type") == "award_page")} |
| Review Article | {sum(1 for s in sources if s.get("source_type") == "review_article")} |
| Retailer Page | {sum(1 for s in sources if s.get("source_type") == "retailer_page")} |
| Other | {sum(1 for s in sources if s.get("source_type") not in ["award_page", "review_article", "retailer_page"])} |"""

    def _generate_verification_checklist(self, verification_results: Dict[str, bool]) -> str:
        """Generate the verification checklist section."""
        if not verification_results:
            return """---

## Verification Checklist

*No verification checks performed*"""

        rows = []
        for check_name, passed in sorted(verification_results.items()):
            status = "[x]" if passed else "[ ]"
            rows.append(f"- {status} {check_name}")

        checks = "\n".join(rows)

        passed_count = sum(1 for v in verification_results.values() if v)
        total_count = len(verification_results)

        return f"""---

## Verification Checklist

**Passed**: {passed_count}/{total_count}

{checks}"""

    def _generate_errors_section(self, errors: List[Dict[str, Any]]) -> str:
        """Generate the errors section."""
        if not errors:
            return """---

## Errors

*No errors encountered*"""

        error_items = []
        for error in errors:
            flow = error.get("flow", "Unknown")
            message = error.get("error", "No message")
            timestamp = error.get("timestamp", "N/A")
            error_items.append(f"- **{flow}** ({timestamp}): {message}")

        error_list = "\n".join(error_items)

        return f"""---

## Errors

**Total Errors**: {len(errors)}

{error_list}"""

    def _generate_footer(self) -> str:
        """Generate the report footer."""
        return """---

## Notes

- All test data has been preserved in the database for manual verification
- Products can be queried by test run timestamp for inspection
- Source tracking records (CrawledSource, ProductSource, ProductFieldSource) remain intact
- Wayback Machine archives may still be processing for recently submitted URLs

---

*Report generated by E2E Test Suite V2*"""


def generate_and_save_report(
    test_run_id: str,
    start_time: datetime,
    end_time: Optional[datetime],
    products: List[Dict[str, Any]],
    sources: List[Dict[str, Any]],
    awards: List[Dict[str, Any]],
    flow_results: Dict[str, Dict[str, Any]],
    verification_results: Dict[str, bool],
    api_calls: Dict[str, int],
    errors: List[Dict[str, Any]],
    base_path: Optional[str] = None,
) -> str:
    """
    Convenience function to generate and save an E2E test report.

    Args:
        test_run_id: Unique identifier for the test run
        start_time: When the test run started
        end_time: When the test run completed
        products: List of product data dictionaries
        sources: List of source data dictionaries
        awards: List of award data dictionaries
        flow_results: Results from each flow execution
        verification_results: Pass/fail for each verification check
        api_calls: Count of API calls per service
        errors: List of errors encountered
        base_path: Base path for the project

    Returns:
        The path where the report was saved
    """
    generator = ReportGenerator(base_path=base_path)

    report_content = generator.generate_report(
        test_run_id=test_run_id,
        start_time=start_time,
        end_time=end_time,
        products=products,
        sources=sources,
        awards=awards,
        flow_results=flow_results,
        verification_results=verification_results,
        api_calls=api_calls,
        errors=errors,
    )

    report_path = generator.save_report(report_content)
    return report_path
