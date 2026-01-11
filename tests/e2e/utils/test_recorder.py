"""
Test Step Recorder for E2E Testing.

Records intermediate outputs from each step of the test flow to a file,
allowing developers to see exactly what each step contributes.

Output file structure:
- Timestamp and test metadata
- Step-by-step outputs with timing
- Final summary

Usage:
    recorder = TestStepRecorder("IWSC Competition Flow")
    recorder.record_step("fetch", "Fetching page", {"url": url})
    recorder.record_step_result("fetch", {"tier_used": 2, "content_length": 50000})
    ...
    recorder.save("tests/e2e/outputs/iwsc_flow_2026-01-10_143022.json")
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StepRecord:
    """Record of a single test step."""
    step_name: str
    description: str
    started_at: str
    completed_at: Optional[str] = None
    duration_ms: Optional[float] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    success: bool = True
    error: Optional[str] = None


@dataclass
class ProductRecord:
    """Record of a single extracted product."""
    index: int
    name: str
    brand: Optional[str]
    is_valid: bool
    rejection_reason: Optional[str] = None
    confidence: float = 0.0
    fields_extracted: List[str] = field(default_factory=list)
    quality_status: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


class TestStepRecorder:
    """
    Records intermediate outputs from each step of an E2E test.

    Creates a detailed log file showing:
    - What data was fetched
    - How the AI extracted products
    - Which products were valid/rejected and why
    - What database records were created
    """

    def __init__(self, test_name: str, output_dir: str = "tests/e2e/outputs"):
        """
        Initialize the recorder.

        Args:
            test_name: Name of the test (e.g., "IWSC Competition Flow")
            output_dir: Directory to save output files
        """
        self.test_name = test_name
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.started_at = datetime.now()
        self.steps: List[StepRecord] = []
        self.products: List[ProductRecord] = []
        self.summary: Dict[str, Any] = {}
        self._current_step: Optional[StepRecord] = None
        self._step_start_time: Optional[float] = None

        # Generate unique filename
        timestamp = self.started_at.strftime("%Y-%m-%d_%H%M%S")
        safe_name = test_name.lower().replace(" ", "_").replace("/", "_")
        self.output_filename = f"{safe_name}_{timestamp}.json"
        self.output_path = self.output_dir / self.output_filename

        logger.info(f"TestStepRecorder initialized: {self.output_path}")

    def start_step(self, step_name: str, description: str, input_data: Optional[Dict[str, Any]] = None):
        """
        Start recording a new step.

        Args:
            step_name: Short identifier for the step (e.g., "fetch", "extract", "validate")
            description: Human-readable description
            input_data: Input parameters for this step
        """
        self._step_start_time = time.time()
        self._current_step = StepRecord(
            step_name=step_name,
            description=description,
            started_at=datetime.now().isoformat(),
            input_data=input_data or {},
        )
        logger.info(f"[STEP] {step_name}: {description}")

    def complete_step(self, output_data: Optional[Dict[str, Any]] = None, success: bool = True, error: Optional[str] = None):
        """
        Complete the current step and record its output.

        Args:
            output_data: Output/result data from this step
            success: Whether the step succeeded
            error: Error message if step failed
        """
        if not self._current_step:
            logger.warning("complete_step called without start_step")
            return

        self._current_step.completed_at = datetime.now().isoformat()
        if self._step_start_time:
            self._current_step.duration_ms = (time.time() - self._step_start_time) * 1000
        self._current_step.output_data = self._sanitize_data(output_data or {})
        self._current_step.success = success
        self._current_step.error = error

        self.steps.append(self._current_step)

        status = "SUCCESS" if success else "FAILED"
        duration = f"{self._current_step.duration_ms:.0f}ms" if self._current_step.duration_ms else "N/A"
        logger.info(f"[STEP] {self._current_step.step_name} {status} ({duration})")

        self._current_step = None
        self._step_start_time = None

    def record_step(self, step_name: str, description: str, input_data: Optional[Dict[str, Any]] = None, output_data: Optional[Dict[str, Any]] = None, success: bool = True, error: Optional[str] = None):
        """
        Record a complete step in one call (for simple steps).

        Args:
            step_name: Short identifier for the step
            description: Human-readable description
            input_data: Input parameters
            output_data: Output/result data
            success: Whether the step succeeded
            error: Error message if step failed
        """
        self.start_step(step_name, description, input_data)
        self.complete_step(output_data, success, error)

    def record_fetch_result(self, url: str, tier_used: int, content_length: int, has_product_indicators: bool, success: bool = True, error: Optional[str] = None, content_preview: Optional[str] = None):
        """
        Record the result of a page fetch operation.

        Args:
            url: URL that was fetched
            tier_used: SmartRouter tier used (1, 2, or 3)
            content_length: Length of fetched content in bytes
            has_product_indicators: Whether content appears to have product data
            success: Whether fetch succeeded
            error: Error message if failed
            content_preview: First N characters of content for debugging
        """
        tier_names = {1: "httpx", 2: "Playwright", 3: "ScrapingBee"}

        self.record_step(
            step_name="fetch",
            description=f"Fetching page via Tier {tier_used} ({tier_names.get(tier_used, 'Unknown')})",
            input_data={
                "url": url,
            },
            output_data={
                "tier_used": tier_used,
                "tier_name": tier_names.get(tier_used, "Unknown"),
                "content_length_bytes": content_length,
                "content_length_kb": round(content_length / 1024, 1),
                "has_product_indicators": has_product_indicators,
                "content_preview": content_preview[:500] if content_preview else None,
            },
            success=success,
            error=error,
        )

    def record_extraction_result(self, total_products: int, valid_products: int, rejected_products: int, extraction_time_ms: Optional[float] = None, ai_response_preview: Optional[str] = None):
        """
        Record the result of AI product extraction.

        Args:
            total_products: Total products returned by AI
            valid_products: Number that passed validation
            rejected_products: Number that failed validation
            extraction_time_ms: Time taken for extraction
            ai_response_preview: Preview of AI response for debugging
        """
        self.record_step(
            step_name="extract",
            description=f"AI extraction returned {total_products} products",
            input_data={},
            output_data={
                "total_products": total_products,
                "valid_products": valid_products,
                "rejected_products": rejected_products,
                "validation_pass_rate": f"{(valid_products / total_products * 100):.1f}%" if total_products > 0 else "N/A",
                "extraction_time_ms": extraction_time_ms,
                "ai_response_preview": ai_response_preview[:1000] if ai_response_preview else None,
            },
        )

    def record_product(self, index: int, product_data: Dict[str, Any], is_valid: bool, rejection_reason: Optional[str] = None, quality_status: Optional[str] = None):
        """
        Record details of a single extracted product.

        Args:
            index: Product index (0-based)
            product_data: Raw product data from extraction
            is_valid: Whether product passed validation
            rejection_reason: Why product was rejected (if applicable)
            quality_status: Quality gate status (skeleton/partial/complete)
        """
        # Extract key fields
        name = product_data.get("name", "Unknown")
        brand = product_data.get("brand")
        confidence = product_data.get("overall_confidence", 0.0)

        # Get list of fields that have values
        fields_extracted = [
            k for k, v in product_data.items()
            if v is not None and v != "" and v != [] and k not in ["field_confidences", "overall_confidence", "source_url"]
        ]

        record = ProductRecord(
            index=index,
            name=name,
            brand=brand,
            is_valid=is_valid,
            rejection_reason=rejection_reason,
            confidence=confidence,
            fields_extracted=fields_extracted,
            quality_status=quality_status,
            raw_data=self._sanitize_data(product_data),
        )
        self.products.append(record)

        status = "VALID" if is_valid else f"REJECTED ({rejection_reason})"
        logger.info(f"  Product {index + 1}: {name[:50]} - {status}")

    def record_database_creation(self, record_type: str, record_id: str, record_data: Optional[Dict[str, Any]] = None):
        """
        Record creation of a database record.

        Args:
            record_type: Type of record (CrawledSource, DiscoveredProduct, ProductAward, etc.)
            record_id: UUID of created record
            record_data: Key data from the record
        """
        self.record_step(
            step_name=f"db_create_{record_type.lower()}",
            description=f"Created {record_type} record",
            output_data={
                "record_type": record_type,
                "record_id": str(record_id),
                "data": self._sanitize_data(record_data or {}),
            },
        )

    def record_quality_assessment(self, product_name: str, status: str, completeness_score: float, missing_fields: List[str], needs_enrichment: bool):
        """
        Record quality gate assessment for a product.

        Args:
            product_name: Name of the product
            status: Quality status (skeleton/partial/complete/enriched)
            completeness_score: 0.0-1.0 completeness score
            missing_fields: List of missing required fields
            needs_enrichment: Whether product needs enrichment
        """
        self.record_step(
            step_name="quality_assess",
            description=f"Quality assessment for {product_name[:30]}",
            output_data={
                "product_name": product_name,
                "status": status,
                "completeness_score": completeness_score,
                "completeness_percent": f"{completeness_score * 100:.0f}%",
                "missing_fields": missing_fields,
                "needs_enrichment": needs_enrichment,
            },
        )

    def record_enrichment_search(self, product_name: str, query: str, urls_found: int, urls: Optional[List[str]] = None):
        """
        Record a SerpAPI enrichment search.

        Args:
            product_name: Name of the product being enriched
            query: Search query used
            urls_found: Number of URLs returned
            urls: List of URLs found (optional, truncated for readability)
        """
        self.record_step(
            step_name="enrichment_search",
            description=f"SerpAPI search for {product_name[:30]}",
            input_data={
                "product_name": product_name,
                "query": query,
            },
            output_data={
                "urls_found": urls_found,
                "urls_preview": urls[:3] if urls else [],
            },
        )

    def record_enrichment_extraction(self, product_name: str, url: str, fields_extracted: List[str], success: bool = True, error: Optional[str] = None):
        """
        Record AI extraction from an enrichment source.

        Args:
            product_name: Name of the product being enriched
            url: Source URL extracted from
            fields_extracted: List of fields successfully extracted
            success: Whether extraction succeeded
            error: Error message if failed
        """
        self.record_step(
            step_name="enrichment_extract",
            description=f"AI extraction from {url[:50]}...",
            input_data={
                "product_name": product_name,
                "url": url,
            },
            output_data={
                "fields_extracted": fields_extracted,
                "fields_count": len(fields_extracted),
            },
            success=success,
            error=error,
        )

    def record_enrichment_result(self, product_name: str, status_before: str, status_after: str, fields_enriched: List[str], sources_used: int, searches_performed: int, time_elapsed: float):
        """
        Record the final enrichment result for a product.

        Args:
            product_name: Name of the product
            status_before: Quality status before enrichment
            status_after: Quality status after enrichment
            fields_enriched: List of fields that were enriched
            sources_used: Number of sources used
            searches_performed: Number of SerpAPI searches performed
            time_elapsed: Time taken in seconds
        """
        self.record_step(
            step_name="enrichment_result",
            description=f"Enrichment complete for {product_name[:30]}",
            output_data={
                "product_name": product_name,
                "status_before": status_before,
                "status_after": status_after,
                "fields_enriched": fields_enriched,
                "fields_enriched_count": len(fields_enriched),
                "sources_used": sources_used,
                "searches_performed": searches_performed,
                "time_elapsed_seconds": round(time_elapsed, 1),
                "status_improved": status_after != status_before,
            },
        )

    def set_summary(self, summary_data: Dict[str, Any]):
        """
        Set the final summary data.

        Args:
            summary_data: Summary statistics and results
        """
        self.summary = self._sanitize_data(summary_data)

    def save(self, custom_path: Optional[str] = None) -> str:
        """
        Save the recorded data to a JSON file.

        Args:
            custom_path: Optional custom file path

        Returns:
            Path to the saved file
        """
        output_path = Path(custom_path) if custom_path else self.output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build output document
        output = {
            "test_name": self.test_name,
            "started_at": self.started_at.isoformat(),
            "completed_at": datetime.now().isoformat(),
            "total_duration_seconds": (datetime.now() - self.started_at).total_seconds(),
            "output_file": str(output_path),
            "steps": [asdict(step) for step in self.steps],
            "products": [asdict(product) for product in self.products],
            "summary": self.summary,
            "statistics": {
                "total_steps": len(self.steps),
                "successful_steps": sum(1 for s in self.steps if s.success),
                "failed_steps": sum(1 for s in self.steps if not s.success),
                "total_products": len(self.products),
                "valid_products": sum(1 for p in self.products if p.is_valid),
                "rejected_products": sum(1 for p in self.products if not p.is_valid),
            },
        }

        # Write to file
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Test recording saved to: {output_path}")

        # Also save a human-readable summary
        summary_path = output_path.with_suffix(".txt")
        self._save_readable_summary(summary_path)

        return str(output_path)

    def _save_readable_summary(self, path: Path):
        """Save a human-readable text summary."""
        lines = [
            "=" * 80,
            f"TEST: {self.test_name}",
            f"Started: {self.started_at.isoformat()}",
            f"Duration: {(datetime.now() - self.started_at).total_seconds():.1f}s",
            "=" * 80,
            "",
            "STEPS:",
            "-" * 40,
        ]

        for i, step in enumerate(self.steps, 1):
            status = "OK" if step.success else "FAIL"
            duration = f"{step.duration_ms:.0f}ms" if step.duration_ms else "N/A"
            lines.append(f"{i}. [{status}] {step.step_name}: {step.description} ({duration})")

            # Add key output data
            if step.output_data:
                for key, value in step.output_data.items():
                    if key not in ["content_preview", "ai_response_preview", "data"]:
                        lines.append(f"      {key}: {value}")

        lines.extend([
            "",
            "PRODUCTS:",
            "-" * 40,
        ])

        for product in self.products:
            status = "VALID" if product.is_valid else f"REJECTED: {product.rejection_reason}"
            lines.append(f"  {product.index + 1}. {product.name}")
            lines.append(f"      Status: {status}")
            lines.append(f"      Confidence: {product.confidence:.2f}")
            lines.append(f"      Fields: {', '.join(product.fields_extracted[:5])}{'...' if len(product.fields_extracted) > 5 else ''}")
            if product.quality_status:
                lines.append(f"      Quality: {product.quality_status}")

        lines.extend([
            "",
            "SUMMARY:",
            "-" * 40,
        ])

        stats = {
            "Total Steps": len(self.steps),
            "Successful Steps": sum(1 for s in self.steps if s.success),
            "Failed Steps": sum(1 for s in self.steps if not s.success),
            "Total Products": len(self.products),
            "Valid Products": sum(1 for p in self.products if p.is_valid),
            "Rejected Products": sum(1 for p in self.products if not p.is_valid),
        }

        for key, value in stats.items():
            lines.append(f"  {key}: {value}")

        lines.append("")
        lines.append("=" * 80)

        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        logger.info(f"Readable summary saved to: {path}")

    def _sanitize_data(self, data: Any) -> Any:
        """
        Sanitize data for JSON serialization.

        Handles UUIDs, datetimes, and other non-serializable types.
        Also truncates very long strings.
        """
        if data is None:
            return None

        if isinstance(data, dict):
            return {k: self._sanitize_data(v) for k, v in data.items()}

        if isinstance(data, list):
            return [self._sanitize_data(item) for item in data]

        if isinstance(data, (str, int, float, bool)):
            # Truncate very long strings
            if isinstance(data, str) and len(data) > 2000:
                return data[:2000] + "... [TRUNCATED]"
            return data

        # Convert other types to string
        return str(data)


def get_recorder(test_name: str) -> TestStepRecorder:
    """
    Factory function to get a TestStepRecorder.

    Args:
        test_name: Name of the test

    Returns:
        Configured TestStepRecorder instance
    """
    return TestStepRecorder(test_name)
