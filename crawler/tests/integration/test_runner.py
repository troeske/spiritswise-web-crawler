"""
Integration Test Runner.

Executes complete crawl-to-enhancement pipeline for medal winner products.
"""
import json
import time
import os
import sys
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from .config import (
    ALL_TEST_SOURCES,
    TOTAL_PRODUCTS,
)
from .scrapingbee_client import ScrapingBeeClient
from .ai_service_client import AIEnhancementClient


class IntegrationTestRunner:
    """Runs complete integration tests for the crawl pipeline."""

    def __init__(self, progress_file: Optional[str] = None):
        self.crawler = ScrapingBeeClient()
        self.ai_service = AIEnhancementClient()
        self.results = {
            "started_at": datetime.now().isoformat(),
            "completed_at": None,
            "categories": {},
            "summary": {
                "total_products": 0,
                "crawl_success": 0,
                "crawl_failed": 0,
                "enhancement_success": 0,
                "enhancement_failed": 0,
                "products_extracted": 0,
            },
            "errors": [],
        }
        self.progress_file = progress_file or str(
            PROJECT_ROOT.parent / "INTEGRATION_TEST_RESULTS.json"
        )

    def _save_progress(self):
        """Save current progress to file for crash recovery."""
        with open(self.progress_file, "w") as f:
            json.dump(self.results, f, indent=2)

    def _log(self, message: str):
        """Log a message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {message}")

    def test_single_product(
        self,
        product_info: Dict[str, Any],
        category: str,
    ) -> Dict[str, Any]:
        """
        Test a single product through the complete pipeline.

        Args:
            product_info: Dict with name, url, medal
            category: Category name (iwsc_whiskey, sfwsc_whiskey, etc.)

        Returns:
            Test result dict
        """
        result = {
            "name": product_info["name"],
            "url": product_info["url"],
            "medal": product_info["medal"],
            "category": category,
            "crawl_success": False,
            "enhancement_success": False,
            "extracted_data": None,
            "errors": [],
            "processing_time_ms": 0,
        }

        start_time = time.time()

        # Step 1: Crawl the page
        self._log(f"  Crawling: {product_info['name'][:40]}...")
        crawl_result = self.crawler.fetch_page(
            product_info["url"],
            render_js=True,
            timeout=45000,
        )

        if not crawl_result["success"]:
            result["errors"].append(f"Crawl failed: {crawl_result.get('error', 'Unknown')}")
            result["processing_time_ms"] = (time.time() - start_time) * 1000
            return result

        result["crawl_success"] = True
        content = crawl_result["content"]

        # Trim content if too large (API limit is 100k chars)
        if len(content) > 90000:
            # Try to extract just the main content
            import re
            # Remove script and style tags
            content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
            content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
            # Remove HTML comments
            content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
            # If still too large, truncate
            if len(content) > 90000:
                content = content[:90000]

        # Determine product type hint based on category
        if "whiskey" in category.lower():
            product_type_hint = "whiskey"
        elif "port" in category.lower():
            product_type_hint = "port_wine"
        else:
            product_type_hint = None

        # Step 2: Send to AI Enhancement Service
        self._log(f"  Enhancing: {product_info['name'][:40]}...")
        enhance_result = self.ai_service.enhance_from_crawler(
            content=content,
            source_url=product_info["url"],
            product_type_hint=product_type_hint,
        )

        if not enhance_result["success"]:
            result["errors"].append(f"Enhancement failed: {enhance_result.get('error', 'Unknown')}")
            result["processing_time_ms"] = (time.time() - start_time) * 1000
            return result

        result["enhancement_success"] = True
        result["extracted_data"] = enhance_result["data"]
        result["processing_time_ms"] = (time.time() - start_time) * 1000

        return result

    def run_category(self, category: str, sources: List[Dict[str, Any]], limit: Optional[int] = None):
        """
        Run tests for a category of products.

        Args:
            category: Category name
            sources: List of source dicts with name, url, medal
            limit: Optional limit on number of products to test
        """
        self._log(f"\n{'='*60}")
        self._log(f"Testing Category: {category.upper()}")
        self._log(f"{'='*60}")

        if limit:
            sources = sources[:limit]

        category_results = {
            "products": [],
            "total": len(sources),
            "crawl_success": 0,
            "enhancement_success": 0,
            "products_extracted": 0,
        }

        for idx, product in enumerate(sources, 1):
            self._log(f"\n[{idx}/{len(sources)}] {product['name']}")

            result = self.test_single_product(product, category)
            category_results["products"].append(result)

            if result["crawl_success"]:
                category_results["crawl_success"] += 1
                self.results["summary"]["crawl_success"] += 1

            if result["enhancement_success"]:
                category_results["enhancement_success"] += 1
                self.results["summary"]["enhancement_success"] += 1

                # Count extracted products
                if result["extracted_data"]:
                    product_count = result["extracted_data"].get("product_count", 1)
                    category_results["products_extracted"] += product_count
                    self.results["summary"]["products_extracted"] += product_count

            if result["errors"]:
                self.results["errors"].extend(result["errors"])
                if not result["crawl_success"]:
                    self.results["summary"]["crawl_failed"] += 1
                elif not result["enhancement_success"]:
                    self.results["summary"]["enhancement_failed"] += 1

            self.results["summary"]["total_products"] += 1

            # Save progress after each product
            self._save_progress()

            # Brief status
            status = "OK" if result["enhancement_success"] else "FAIL"
            self._log(f"  Status: {status} ({result['processing_time_ms']:.0f}ms)")

        self.results["categories"][category] = category_results

        # Category summary
        self._log(f"\nCategory Summary: {category}")
        self._log(f"  Crawl Success: {category_results['crawl_success']}/{category_results['total']}")
        self._log(f"  Enhancement Success: {category_results['enhancement_success']}/{category_results['total']}")
        self._log(f"  Products Extracted: {category_results['products_extracted']}")

    def run_all(self, limit_per_category: Optional[int] = None):
        """
        Run all integration tests.

        Args:
            limit_per_category: Optional limit on products per category (for testing)
        """
        self._log("\n" + "="*60)
        self._log("SPIRITSWISE INTEGRATION TEST SUITE")
        self._log(f"Started: {self.results['started_at']}")
        self._log(f"Total Products: {TOTAL_PRODUCTS}")
        if limit_per_category:
            self._log(f"Limit per Category: {limit_per_category}")
        self._log("="*60)

        for category, sources in ALL_TEST_SOURCES.items():
            self.run_category(category, sources, limit=limit_per_category)

        self.results["completed_at"] = datetime.now().isoformat()
        self._save_progress()

        # Final summary
        self._log("\n" + "="*60)
        self._log("FINAL SUMMARY")
        self._log("="*60)
        self._log(f"Total Products Tested: {self.results['summary']['total_products']}")
        self._log(f"Crawl Success Rate: {self.results['summary']['crawl_success']}/{self.results['summary']['total_products']}")
        self._log(f"Enhancement Success Rate: {self.results['summary']['enhancement_success']}/{self.results['summary']['total_products']}")
        self._log(f"Total Products Extracted: {self.results['summary']['products_extracted']}")
        self._log(f"Total Errors: {len(self.results['errors'])}")
        self._log(f"\nResults saved to: {self.progress_file}")

        return self.results


def main():
    """Run integration tests."""
    import argparse

    parser = argparse.ArgumentParser(description="Run integration tests")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit products per category (for quick testing)",
    )
    parser.add_argument(
        "--category",
        type=str,
        default=None,
        choices=list(ALL_TEST_SOURCES.keys()),
        help="Run only a specific category",
    )
    args = parser.parse_args()

    runner = IntegrationTestRunner()

    if args.category:
        sources = ALL_TEST_SOURCES[args.category]
        runner.run_category(args.category, sources, limit=args.limit)
    else:
        runner.run_all(limit_per_category=args.limit)


if __name__ == "__main__":
    main()
