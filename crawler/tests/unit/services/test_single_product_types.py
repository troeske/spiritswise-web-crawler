"""
Unit tests for Single Product data types.

Task 1.3-1.4: Tests for SingleProductResult and SingleProductJobResult.

Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 7
"""

from datetime import datetime
from unittest import TestCase
from uuid import uuid4

from crawler.services.single_product_types import (
    SingleProductResult,
    SingleProductJobResult,
)


class SingleProductResultTests(TestCase):
    """Tests for SingleProductResult dataclass (Task 1.3)."""

    def test_default_values(self):
        """Test SingleProductResult default values."""
        result = SingleProductResult()

        self.assertFalse(result.success)
        self.assertIsNone(result.product_id)
        self.assertEqual(result.product_name, "")
        self.assertTrue(result.is_new_product)
        self.assertEqual(result.match_method, "none")
        self.assertEqual(result.match_confidence, 0.0)
        self.assertEqual(result.status_before, "")
        self.assertEqual(result.status_after, "")
        self.assertEqual(result.ecp_before, 0.0)
        self.assertEqual(result.ecp_after, 0.0)
        self.assertFalse(result.enrichment_completed)
        self.assertEqual(result.fields_enriched, [])
        self.assertEqual(result.sources_used, [])
        self.assertEqual(result.field_provenance, {})
        self.assertEqual(result.extraction_time_seconds, 0.0)
        self.assertEqual(result.enrichment_time_seconds, 0.0)
        self.assertEqual(result.total_time_seconds, 0.0)
        self.assertIsNone(result.error)
        self.assertEqual(result.warnings, [])

    def test_custom_values(self):
        """Test SingleProductResult with custom values."""
        product_id = uuid4()
        result = SingleProductResult(
            success=True,
            product_id=product_id,
            product_name="Macallan 18",
            is_new_product=False,
            match_method="fingerprint",
            match_confidence=0.95,
            status_before="PARTIAL",
            status_after="ENRICHED",
            ecp_before=25.0,
            ecp_after=75.0,
            enrichment_completed=True,
            fields_enriched=["nose_description", "palate_description"],
            sources_used=["https://example.com/review"],
            field_provenance={"nose_description": "https://example.com/review"},
            extraction_time_seconds=1.5,
            enrichment_time_seconds=3.0,
            total_time_seconds=4.5,
        )

        self.assertTrue(result.success)
        self.assertEqual(result.product_id, product_id)
        self.assertEqual(result.product_name, "Macallan 18")
        self.assertFalse(result.is_new_product)
        self.assertEqual(result.match_method, "fingerprint")
        self.assertEqual(result.match_confidence, 0.95)

    def test_to_dict(self):
        """Test SingleProductResult to_dict serialization."""
        product_id = uuid4()
        result = SingleProductResult(
            success=True,
            product_id=product_id,
            product_name="Test Whiskey",
            fields_enriched=["name", "brand"],
        )

        data = result.to_dict()

        self.assertIsInstance(data, dict)
        self.assertEqual(data["success"], True)
        self.assertEqual(data["product_id"], str(product_id))
        self.assertEqual(data["product_name"], "Test Whiskey")
        self.assertEqual(data["fields_enriched"], ["name", "brand"])

    def test_to_dict_none_product_id(self):
        """Test to_dict handles None product_id."""
        result = SingleProductResult(success=False)

        data = result.to_dict()

        self.assertIsNone(data["product_id"])


class SingleProductJobResultTests(TestCase):
    """Tests for SingleProductJobResult dataclass (Task 1.4)."""

    def test_default_values(self):
        """Test SingleProductJobResult default values."""
        result = SingleProductJobResult()

        self.assertIsNone(result.job_id)
        self.assertIsNone(result.schedule_id)
        self.assertEqual(result.products_processed, 0)
        self.assertEqual(result.products_new, 0)
        self.assertEqual(result.products_existing, 0)
        self.assertEqual(result.products_enriched, 0)
        self.assertEqual(result.products_failed, 0)
        self.assertEqual(result.results, [])
        self.assertIsNone(result.start_time)
        self.assertIsNone(result.end_time)
        self.assertEqual(result.duration_seconds, 0.0)
        self.assertTrue(result.success)
        self.assertEqual(result.errors, [])

    def test_add_result_new_product(self):
        """Test add_result increments counters for new product."""
        job_result = SingleProductJobResult()
        product_result = SingleProductResult(
            success=True,
            is_new_product=True,
            enrichment_completed=True,
        )

        job_result.add_result(product_result)

        self.assertEqual(job_result.products_processed, 1)
        self.assertEqual(job_result.products_new, 1)
        self.assertEqual(job_result.products_existing, 0)
        self.assertEqual(job_result.products_enriched, 1)
        self.assertEqual(job_result.products_failed, 0)
        self.assertEqual(len(job_result.results), 1)

    def test_add_result_existing_product(self):
        """Test add_result increments counters for existing product."""
        job_result = SingleProductJobResult()
        product_result = SingleProductResult(
            success=True,
            is_new_product=False,
            enrichment_completed=True,
        )

        job_result.add_result(product_result)

        self.assertEqual(job_result.products_processed, 1)
        self.assertEqual(job_result.products_new, 0)
        self.assertEqual(job_result.products_existing, 1)
        self.assertEqual(job_result.products_enriched, 1)
        self.assertEqual(job_result.products_failed, 0)

    def test_add_result_failed(self):
        """Test add_result increments failure counter."""
        job_result = SingleProductJobResult()
        product_result = SingleProductResult(
            success=False,
            error="Fetch failed",
        )

        job_result.add_result(product_result)

        self.assertEqual(job_result.products_processed, 1)
        self.assertEqual(job_result.products_failed, 1)
        self.assertEqual(job_result.errors, ["Fetch failed"])

    def test_finalize(self):
        """Test finalize sets end time and duration."""
        job_result = SingleProductJobResult()
        job_result.start_time = datetime.now()

        job_result.finalize()

        self.assertIsNotNone(job_result.end_time)
        self.assertGreaterEqual(job_result.duration_seconds, 0.0)

    def test_to_dict(self):
        """Test SingleProductJobResult to_dict serialization."""
        job_id = uuid4()
        schedule_id = uuid4()

        job_result = SingleProductJobResult(
            job_id=job_id,
            schedule_id=schedule_id,
            products_processed=5,
            products_new=3,
            products_existing=2,
            start_time=datetime(2026, 1, 1, 12, 0, 0),
        )

        data = job_result.to_dict()

        self.assertIsInstance(data, dict)
        self.assertEqual(data["job_id"], str(job_id))
        self.assertEqual(data["schedule_id"], str(schedule_id))
        self.assertEqual(data["products_processed"], 5)
        self.assertEqual(data["start_time"], "2026-01-01T12:00:00")

    def test_success_flag_partial_failures(self):
        """Test success flag with partial failures."""
        job_result = SingleProductJobResult()

        # Add 3 successes
        for _ in range(3):
            job_result.add_result(SingleProductResult(success=True))

        # Add 1 failure
        job_result.add_result(SingleProductResult(success=False, error="Error"))

        job_result.finalize()

        # Should still be success since more succeeded than failed
        self.assertTrue(job_result.success)

    def test_success_flag_all_failures(self):
        """Test success flag when all fail."""
        job_result = SingleProductJobResult()

        # Add only failures
        job_result.add_result(SingleProductResult(success=False, error="Error 1"))
        job_result.add_result(SingleProductResult(success=False, error="Error 2"))

        job_result.finalize()

        # Should be failure
        self.assertFalse(job_result.success)
