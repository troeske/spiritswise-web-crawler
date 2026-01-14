"""
Results Exporter for E2E Tests.

This module provides comprehensive results export for E2E tests,
including full product data, source tracking, and domain intelligence metrics.

Output format designed for:
1. Verification of enrichment quality
2. Source provenance tracking
3. Domain intelligence analysis

Usage:
    exporter = ResultsExporter("domain_intelligence_e2e")

    # During test execution
    exporter.add_product({
        "id": "uuid",
        "name": "Ardbeg 10",
        ...
    })
    exporter.add_source_used("uuid", {"url": "...", "fields": [...]})
    exporter.add_domain_profile({...})
    exporter.save()  # Incremental save

    # At end
    exporter.set_metrics({...})
    exporter.finalize()
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class ResultsExporter:
    """
    Comprehensive results exporter for E2E tests.

    Exports all product data, source tracking, and domain intelligence
    to timestamped JSON files for verification.
    """

    BASE_DIR = Path(__file__).parent.parent / "outputs"

    def __init__(self, test_name: str):
        """
        Initialize results exporter.

        Args:
            test_name: Name of the test for file naming
        """
        self.test_name = test_name
        self.timestamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
        self.filepath = self.BASE_DIR / f"e2e_results_{test_name}_{self.timestamp}.json"

        # Ensure output directory exists
        self.BASE_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize results structure
        self._results: Dict[str, Any] = {
            "test_name": test_name,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": None,
            "status": "RUNNING",
            "products": [],
            "domain_profiles": [],
            "metrics": {
                "total_products": 0,
                "products_by_status": {},
                "products_by_flow": {},
                "baseline_achieved": 0,
                "average_ecp": 0.0,
                "tier_distribution": {"tier_1": 0, "tier_2": 0, "tier_3": 0},
                "sources_per_product_avg": 0.0,
                "cross_contamination_count": 0,
            },
            "errors": [],
        }

    def add_product(self, product_data: Dict[str, Any]) -> None:
        """
        Add a product with full field data.

        Expected product_data structure:
        {
            "id": str,
            "name": str,
            "brand": str,
            "product_type": "whiskey" | "port_wine",
            "status": "SKELETON" | "PARTIAL" | "BASELINE" | "ENRICHED" | "COMPLETE",
            "ecp_score": float,
            "flow": "competition" | "generic_search" | "single_product",
            "fields_populated": [str],
            "field_values": {
                "abv": float,
                "description": str,
                "nose_description": str,
                "palate_flavors": [str],
                "finish_description": str,
                "distillery": str,
                "region": str,
                "age_statement": int,
                # ... all fields with values
            },
            "sources_used": [],  # Will be populated via add_source_used
            "domain_intelligence": {
                "primary_domain": str,
                "tier_used": int,
                "escalation_reason": str | None,
                "profile_flags": {
                    "likely_js_heavy": bool,
                    "likely_bot_protected": bool,
                    "likely_slow": bool
                }
            },
            "enrichment_details": {
                "step_1_completed": bool,
                "step_1_url": str,
                "step_2_completed": bool,
                "step_2_sources": [str],
                "fields_enriched": [str]
            }
        }
        """
        # Ensure sources_used list exists
        if "sources_used" not in product_data:
            product_data["sources_used"] = []

        # Add timestamp
        product_data["added_at"] = datetime.utcnow().isoformat()

        # Check if product already exists (by ID or name+brand)
        product_id = product_data.get("id")
        existing_idx = self._find_product_index(product_id, product_data.get("name"), product_data.get("brand"))

        if existing_idx is not None:
            # Merge sources from existing
            existing_sources = self._results["products"][existing_idx].get("sources_used", [])
            new_sources = product_data.get("sources_used", [])
            product_data["sources_used"] = existing_sources + new_sources
            self._results["products"][existing_idx] = product_data
        else:
            self._results["products"].append(product_data)

        self._update_metrics()
        self.save()

    def _find_product_index(
        self, product_id: Optional[str], name: Optional[str], brand: Optional[str]
    ) -> Optional[int]:
        """Find existing product by ID or name+brand."""
        for idx, p in enumerate(self._results["products"]):
            # Match by ID
            if product_id and p.get("id") == product_id:
                return idx
            # Match by name + brand
            if name and brand:
                if p.get("name") == name and p.get("brand") == brand:
                    return idx
        return None

    def update_product(self, product_id: str, updates: Dict[str, Any]) -> None:
        """
        Update an existing product.

        Args:
            product_id: ID of product to update
            updates: Dictionary of fields to update
        """
        for idx, p in enumerate(self._results["products"]):
            if p.get("id") == product_id:
                self._results["products"][idx].update(updates)
                self._results["products"][idx]["updated_at"] = datetime.utcnow().isoformat()
                break

        self._update_metrics()
        self.save()

    def add_source_used(
        self,
        product_id: str,
        source_data: Dict[str, Any],
    ) -> None:
        """
        Add a source used for a product.

        Args:
            product_id: ID of the product
            source_data: Source information:
                {
                    "url": str,
                    "source_type": "competition" | "producer_page" | "review_site" | "product_page",
                    "tier_used": int,
                    "fields_from_source": [str],
                    "domain": str,
                    "fetch_time_ms": int,
                    "extraction_confidence": float
                }
        """
        for product in self._results["products"]:
            if product.get("id") == product_id:
                if "sources_used" not in product:
                    product["sources_used"] = []
                source_data["added_at"] = datetime.utcnow().isoformat()
                product["sources_used"].append(source_data)
                break

        self._update_metrics()
        self.save()

    def add_domain_profile(self, profile_data: Dict[str, Any]) -> None:
        """
        Add or update a domain profile.

        Expected profile_data structure:
        {
            "domain": str,
            "likely_js_heavy": bool,
            "likely_bot_protected": bool,
            "likely_slow": bool,
            "tier1_success_rate": float,
            "tier2_success_rate": float,
            "tier3_success_rate": float,
            "recommended_tier": int,
            "timeout_count": int,
            "success_count": int,
            "failure_count": int,
            "avg_response_time_ms": float
        }
        """
        domain = profile_data.get("domain")

        # Update existing or add new
        existing_idx = None
        for idx, p in enumerate(self._results["domain_profiles"]):
            if p.get("domain") == domain:
                existing_idx = idx
                break

        if existing_idx is not None:
            self._results["domain_profiles"][existing_idx] = profile_data
        else:
            self._results["domain_profiles"].append(profile_data)

        self.save()

    def set_metrics(self, metrics: Dict[str, Any]) -> None:
        """
        Set or update metrics.

        Args:
            metrics: Metrics dictionary to merge
        """
        self._results["metrics"].update(metrics)
        self.save()

    def add_error(self, error_data: Dict[str, Any]) -> None:
        """
        Add an error to results.

        Args:
            error_data: Error information
        """
        error_data["timestamp"] = datetime.utcnow().isoformat()
        self._results["errors"].append(error_data)
        self.save()

    def _update_metrics(self) -> None:
        """Update metrics based on current products."""
        products = self._results["products"]

        # Total products
        self._results["metrics"]["total_products"] = len(products)

        # By status
        status_counts = {}
        for p in products:
            status = p.get("status", "UNKNOWN")
            status_counts[status] = status_counts.get(status, 0) + 1
        self._results["metrics"]["products_by_status"] = status_counts

        # By flow
        flow_counts = {}
        for p in products:
            flow = p.get("flow", "unknown")
            flow_counts[flow] = flow_counts.get(flow, 0) + 1
        self._results["metrics"]["products_by_flow"] = flow_counts

        # Baseline achieved
        baseline_statuses = {"BASELINE", "ENRICHED", "COMPLETE"}
        baseline_count = sum(
            1 for p in products if p.get("status") in baseline_statuses
        )
        self._results["metrics"]["baseline_achieved"] = baseline_count

        # Average ECP
        ecp_scores = [p.get("ecp_score", 0) for p in products if p.get("ecp_score")]
        if ecp_scores:
            self._results["metrics"]["average_ecp"] = sum(ecp_scores) / len(ecp_scores)

        # Tier distribution
        tier_counts = {"tier_1": 0, "tier_2": 0, "tier_3": 0}
        for p in products:
            di = p.get("domain_intelligence", {})
            tier = di.get("tier_used", 1)
            tier_key = f"tier_{tier}"
            if tier_key in tier_counts:
                tier_counts[tier_key] += 1
        self._results["metrics"]["tier_distribution"] = tier_counts

        # Sources per product average
        source_counts = [len(p.get("sources_used", [])) for p in products]
        if source_counts:
            self._results["metrics"]["sources_per_product_avg"] = (
                sum(source_counts) / len(source_counts)
            )

    def save(self) -> None:
        """Save current results to file (incremental)."""
        self._results["last_saved"] = datetime.utcnow().isoformat()

        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(self._results, f, indent=2, default=str)

    def finalize(self, status: str = "COMPLETED") -> str:
        """
        Finalize results with completion timestamp.

        Args:
            status: Final status (COMPLETED, FAILED, PARTIAL)

        Returns:
            Path to the results file
        """
        self._results["completed_at"] = datetime.utcnow().isoformat()
        self._results["status"] = status
        self._update_metrics()
        self.save()

        return str(self.filepath)

    def get_filepath(self) -> str:
        """Get the output file path."""
        return str(self.filepath)

    def get_results(self) -> Dict[str, Any]:
        """Get current results dictionary."""
        return self._results.copy()

    def get_products(self) -> List[Dict[str, Any]]:
        """Get list of products."""
        return self._results.get("products", [])

    def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """Get a product by ID."""
        for p in self._results["products"]:
            if p.get("id") == product_id:
                return p
        return None

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return self._results.get("metrics", {})

    def get_domain_profiles(self) -> List[Dict[str, Any]]:
        """Get domain profiles."""
        return self._results.get("domain_profiles", [])


class SummaryGenerator:
    """
    Generates comprehensive summary reports from test results.
    """

    def __init__(self, results: Dict[str, Any]):
        """
        Initialize with test results.

        Args:
            results: Results dictionary from ResultsExporter
        """
        self.results = results

    def generate_markdown_summary(self) -> str:
        """Generate Markdown summary report."""
        products = self.results.get("products", [])
        metrics = self.results.get("metrics", {})
        domain_profiles = self.results.get("domain_profiles", [])
        errors = self.results.get("errors", [])

        lines = [
            "# E2E Test Results Summary",
            "",
            f"**Test:** {self.results.get('test_name')}",
            f"**Started:** {self.results.get('started_at')}",
            f"**Completed:** {self.results.get('completed_at')}",
            f"**Status:** {self.results.get('status')}",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            f"- **Total Products:** {metrics.get('total_products', 0)}",
            f"- **Baseline Achieved:** {metrics.get('baseline_achieved', 0)}",
            f"- **Average ECP:** {metrics.get('average_ecp', 0):.1f}%",
            f"- **Cross-Contamination:** {metrics.get('cross_contamination_count', 0)}",
            "",
            "### Status Distribution",
            "",
            "| Status | Count |",
            "|--------|-------|",
        ]

        for status, count in metrics.get("products_by_status", {}).items():
            lines.append(f"| {status} | {count} |")

        lines.extend([
            "",
            "### Flow Distribution",
            "",
            "| Flow | Count |",
            "|------|-------|",
        ])

        for flow, count in metrics.get("products_by_flow", {}).items():
            lines.append(f"| {flow} | {count} |")

        lines.extend([
            "",
            "### Tier Usage",
            "",
            "| Tier | Count |",
            "|------|-------|",
        ])

        tier_dist = metrics.get("tier_distribution", {})
        for tier, count in tier_dist.items():
            lines.append(f"| {tier.replace('_', ' ').title()} | {count} |")

        lines.extend([
            "",
            "---",
            "",
            "## Domain Intelligence Analysis",
            "",
            f"**Profiles Created:** {len(domain_profiles)}",
            "",
        ])

        if domain_profiles:
            # JS-heavy domains
            js_heavy = [p["domain"] for p in domain_profiles if p.get("likely_js_heavy")]
            if js_heavy:
                lines.append("**JS-Heavy Domains:**")
                for d in js_heavy:
                    lines.append(f"- {d}")
                lines.append("")

            # Bot-protected domains
            bot_protected = [p["domain"] for p in domain_profiles if p.get("likely_bot_protected")]
            if bot_protected:
                lines.append("**Bot-Protected Domains:**")
                for d in bot_protected:
                    lines.append(f"- {d}")
                lines.append("")

        lines.extend([
            "---",
            "",
            "## Product Details",
            "",
        ])

        for i, product in enumerate(products[:20], 1):  # Limit to 20 for readability
            lines.extend([
                f"### {i}. {product.get('name', 'Unknown')}",
                "",
                f"- **Brand:** {product.get('brand', 'Unknown')}",
                f"- **Type:** {product.get('product_type', 'Unknown')}",
                f"- **Status:** {product.get('status', 'Unknown')}",
                f"- **ECP:** {product.get('ecp_score', 0):.1f}%",
                f"- **Flow:** {product.get('flow', 'Unknown')}",
                f"- **Sources:** {len(product.get('sources_used', []))}",
                "",
            ])

            # Key fields
            field_values = product.get("field_values", {})
            if field_values.get("abv"):
                lines.append(f"- **ABV:** {field_values['abv']}%")
            if field_values.get("description"):
                desc = field_values["description"][:100] + "..." if len(str(field_values.get("description", ""))) > 100 else field_values.get("description", "")
                lines.append(f"- **Description:** {desc}")
            lines.append("")

        if len(products) > 20:
            lines.append(f"*... and {len(products) - 20} more products*")
            lines.append("")

        # Errors
        if errors:
            lines.extend([
                "---",
                "",
                "## Errors",
                "",
            ])
            for error in errors:
                lines.append(f"- [{error.get('timestamp')}] {error.get('message', 'Unknown error')}")
            lines.append("")

        return "\n".join(lines)

    def generate_json_summary(self) -> Dict[str, Any]:
        """Generate JSON summary for programmatic access."""
        return {
            "test_name": self.results.get("test_name"),
            "started_at": self.results.get("started_at"),
            "completed_at": self.results.get("completed_at"),
            "status": self.results.get("status"),
            "metrics": self.results.get("metrics"),
            "domain_profiles_count": len(self.results.get("domain_profiles", [])),
            "errors_count": len(self.results.get("errors", [])),
            "products_summary": [
                {
                    "name": p.get("name"),
                    "brand": p.get("brand"),
                    "status": p.get("status"),
                    "ecp_score": p.get("ecp_score"),
                    "sources_count": len(p.get("sources_used", [])),
                }
                for p in self.results.get("products", [])
            ],
        }
