"""
Data Verification Utilities for E2E Tests.

Provides utilities for verifying:
- Product required fields
- Palate flavors population
- Source tracking records
- Award records
- Wayback archival status
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """
    Result of a verification check.

    Attributes:
        passed: Whether the verification passed
        check_name: Name of the verification check
        message: Description of the result
        details: Additional details about the check
    """

    passed: bool
    check_name: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


class DataVerifier:
    """
    Verifies data integrity and completeness for E2E tests.

    Provides methods for:
    - Verifying product has required fields
    - Verifying palate_flavors populated
    - Verifying source tracking records exist
    - Verifying award records
    - Verifying wayback archival
    """

    # Required fields for different status levels
    SKELETON_REQUIRED_FIELDS: Set[str] = {"name"}
    PARTIAL_REQUIRED_FIELDS: Set[str] = {"name", "brand"}
    COMPLETE_REQUIRED_FIELDS: Set[str] = {"name", "brand", "abv", "description"}

    # Fields that should be populated after enrichment
    ENRICHMENT_EXPECTED_FIELDS: Set[str] = {
        "palate_flavors",
        "nose_description",
        "finish_description",
    }

    def __init__(self):
        """Initialize the data verifier."""
        self._results: List[VerificationResult] = []

    def clear_results(self) -> None:
        """Clear all verification results."""
        self._results = []

    def get_results(self) -> List[VerificationResult]:
        """Get all verification results."""
        return self._results.copy()

    def get_passed_count(self) -> int:
        """Get count of passed verifications."""
        return sum(1 for r in self._results if r.passed)

    def get_failed_count(self) -> int:
        """Get count of failed verifications."""
        return sum(1 for r in self._results if not r.passed)

    def verify_product_required_fields(
        self,
        product_data: Dict[str, Any],
        required_fields: Optional[Set[str]] = None,
    ) -> VerificationResult:
        """
        Verify a product has required fields populated.

        Args:
            product_data: Dictionary of product field values
            required_fields: Set of required field names (defaults to SKELETON_REQUIRED_FIELDS)

        Returns:
            VerificationResult with pass/fail status
        """
        required = required_fields or self.SKELETON_REQUIRED_FIELDS
        missing = []
        populated = []

        for field_name in required:
            value = product_data.get(field_name)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.append(field_name)
            else:
                populated.append(field_name)

        passed = len(missing) == 0
        product_name = product_data.get("name", "Unknown")

        result = VerificationResult(
            passed=passed,
            check_name=f"product_required_fields:{product_name}",
            message=f"Product '{product_name}' {'has' if passed else 'missing'} required fields",
            details={
                "product_name": product_name,
                "required_fields": list(required),
                "populated_fields": populated,
                "missing_fields": missing,
            },
        )

        self._results.append(result)
        return result

    def verify_palate_flavors_populated(
        self,
        product_data: Dict[str, Any],
    ) -> VerificationResult:
        """
        Verify a product has palate_flavors array populated.

        Args:
            product_data: Dictionary of product field values

        Returns:
            VerificationResult with pass/fail status
        """
        palate_flavors = product_data.get("palate_flavors")
        product_name = product_data.get("name", "Unknown")

        # Check if palate_flavors is a non-empty list
        passed = (
            palate_flavors is not None
            and isinstance(palate_flavors, list)
            and len(palate_flavors) > 0
        )

        result = VerificationResult(
            passed=passed,
            check_name=f"palate_flavors:{product_name}",
            message=f"Product '{product_name}' {'has' if passed else 'missing'} palate_flavors",
            details={
                "product_name": product_name,
                "palate_flavors": palate_flavors,
                "flavor_count": len(palate_flavors) if palate_flavors else 0,
            },
        )

        self._results.append(result)
        return result

    def verify_source_tracking_exists(
        self,
        product_id: UUID,
        min_sources: int = 1,
    ) -> VerificationResult:
        """
        Verify source tracking records exist for a product.

        Args:
            product_id: UUID of the product
            min_sources: Minimum number of sources expected

        Returns:
            VerificationResult with pass/fail status
        """
        from crawler.models import ProductSource

        sources = ProductSource.objects.filter(product_id=product_id)
        source_count = sources.count()
        passed = source_count >= min_sources

        result = VerificationResult(
            passed=passed,
            check_name=f"source_tracking:{product_id}",
            message=f"Product has {source_count} source(s), expected >= {min_sources}",
            details={
                "product_id": str(product_id),
                "source_count": source_count,
                "min_sources": min_sources,
                "source_ids": [str(s.source_id) for s in sources],
            },
        )

        self._results.append(result)
        return result

    def verify_product_source_linkage(
        self,
        product_id: UUID,
    ) -> VerificationResult:
        """
        Verify ProductSource records have proper linkage.

        Args:
            product_id: UUID of the product

        Returns:
            VerificationResult with pass/fail status
        """
        from crawler.models import ProductSource, CrawledSource

        sources = ProductSource.objects.filter(product_id=product_id).select_related("source")
        valid_links = []
        invalid_links = []

        for ps in sources:
            if ps.source and ps.source.url:
                valid_links.append(str(ps.source_id))
            else:
                invalid_links.append(str(ps.source_id))

        passed = len(sources) > 0 and len(invalid_links) == 0

        result = VerificationResult(
            passed=passed,
            check_name=f"product_source_linkage:{product_id}",
            message=f"Product has {len(valid_links)} valid source link(s)",
            details={
                "product_id": str(product_id),
                "valid_links": valid_links,
                "invalid_links": invalid_links,
            },
        )

        self._results.append(result)
        return result

    def verify_field_provenance_exists(
        self,
        product_id: UUID,
        expected_fields: Optional[Set[str]] = None,
    ) -> VerificationResult:
        """
        Verify ProductFieldSource records exist for a product.

        Args:
            product_id: UUID of the product
            expected_fields: Optional set of fields that should have provenance

        Returns:
            VerificationResult with pass/fail status
        """
        from crawler.models import ProductFieldSource

        field_sources = ProductFieldSource.objects.filter(product_id=product_id)
        field_names = set(field_sources.values_list("field_name", flat=True))

        if expected_fields:
            missing = expected_fields - field_names
            passed = len(missing) == 0
        else:
            passed = len(field_names) > 0

        result = VerificationResult(
            passed=passed,
            check_name=f"field_provenance:{product_id}",
            message=f"Product has provenance for {len(field_names)} field(s)",
            details={
                "product_id": str(product_id),
                "fields_with_provenance": list(field_names),
                "expected_fields": list(expected_fields) if expected_fields else None,
                "missing_fields": list(expected_fields - field_names) if expected_fields else None,
            },
        )

        self._results.append(result)
        return result

    def verify_award_records(
        self,
        product_id: UUID,
        expected_competition: Optional[str] = None,
        expected_year: Optional[int] = None,
    ) -> VerificationResult:
        """
        Verify ProductAward records exist for a product.

        Args:
            product_id: UUID of the product
            expected_competition: Optional competition name to verify
            expected_year: Optional year to verify

        Returns:
            VerificationResult with pass/fail status
        """
        from crawler.models import ProductAward

        awards = ProductAward.objects.filter(product_id=product_id)
        award_count = awards.count()

        # Check for specific competition/year if provided
        matching_awards = awards
        if expected_competition:
            matching_awards = matching_awards.filter(competition__icontains=expected_competition)
        if expected_year:
            matching_awards = matching_awards.filter(year=expected_year)

        passed = matching_awards.exists()

        result = VerificationResult(
            passed=passed,
            check_name=f"award_records:{product_id}",
            message=f"Product has {award_count} award(s), {matching_awards.count()} matching criteria",
            details={
                "product_id": str(product_id),
                "total_awards": award_count,
                "matching_awards": matching_awards.count(),
                "expected_competition": expected_competition,
                "expected_year": expected_year,
                "awards": [
                    {
                        "competition": a.competition,
                        "year": a.year,
                        "medal": a.medal,
                    }
                    for a in awards
                ],
            },
        )

        self._results.append(result)
        return result

    def verify_wayback_archival(
        self,
        source_id: UUID,
    ) -> VerificationResult:
        """
        Verify a CrawledSource has been archived to Wayback Machine.

        Args:
            source_id: UUID of the CrawledSource

        Returns:
            VerificationResult with pass/fail status
        """
        from crawler.models import CrawledSource, WaybackStatusChoices

        try:
            source = CrawledSource.objects.get(pk=source_id)
        except CrawledSource.DoesNotExist:
            result = VerificationResult(
                passed=False,
                check_name=f"wayback_archival:{source_id}",
                message="CrawledSource not found",
                details={"source_id": str(source_id)},
            )
            self._results.append(result)
            return result

        passed = (
            source.wayback_status == WaybackStatusChoices.SAVED
            and source.wayback_url is not None
        )

        result = VerificationResult(
            passed=passed,
            check_name=f"wayback_archival:{source_id}",
            message=f"Source wayback_status: {source.wayback_status}",
            details={
                "source_id": str(source_id),
                "url": source.url,
                "wayback_status": source.wayback_status,
                "wayback_url": source.wayback_url,
                "wayback_saved_at": source.wayback_saved_at.isoformat() if source.wayback_saved_at else None,
            },
        )

        self._results.append(result)
        return result

    def verify_crawled_source_content(
        self,
        source_id: UUID,
    ) -> VerificationResult:
        """
        Verify a CrawledSource has raw_content stored.

        Args:
            source_id: UUID of the CrawledSource

        Returns:
            VerificationResult with pass/fail status
        """
        from crawler.models import CrawledSource

        try:
            source = CrawledSource.objects.get(pk=source_id)
        except CrawledSource.DoesNotExist:
            result = VerificationResult(
                passed=False,
                check_name=f"source_content:{source_id}",
                message="CrawledSource not found",
                details={"source_id": str(source_id)},
            )
            self._results.append(result)
            return result

        has_content = source.raw_content is not None and len(source.raw_content) > 0
        passed = has_content or source.raw_content_cleared

        result = VerificationResult(
            passed=passed,
            check_name=f"source_content:{source_id}",
            message=f"Source {'has content' if has_content else 'content cleared' if source.raw_content_cleared else 'missing content'}",
            details={
                "source_id": str(source_id),
                "url": source.url,
                "has_raw_content": has_content,
                "content_length": len(source.raw_content) if source.raw_content else 0,
                "raw_content_cleared": source.raw_content_cleared,
            },
        )

        self._results.append(result)
        return result

    def verify_extraction_confidence(
        self,
        product_id: UUID,
        min_confidence: float = 0.5,
    ) -> VerificationResult:
        """
        Verify extraction confidence values are within expected range.

        Args:
            product_id: UUID of the product
            min_confidence: Minimum acceptable confidence value

        Returns:
            VerificationResult with pass/fail status
        """
        from crawler.models import ProductFieldSource

        field_sources = ProductFieldSource.objects.filter(product_id=product_id)
        confidences = []
        low_confidence_fields = []

        for fs in field_sources:
            conf = float(fs.confidence)
            confidences.append(conf)
            if conf < min_confidence:
                low_confidence_fields.append({
                    "field_name": fs.field_name,
                    "confidence": conf,
                })

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0
        passed = len(low_confidence_fields) == 0 or len(confidences) == 0

        result = VerificationResult(
            passed=passed,
            check_name=f"extraction_confidence:{product_id}",
            message=f"Average confidence: {avg_confidence:.2f}, low confidence fields: {len(low_confidence_fields)}",
            details={
                "product_id": str(product_id),
                "avg_confidence": avg_confidence,
                "min_confidence": min_confidence,
                "total_fields": len(confidences),
                "low_confidence_fields": low_confidence_fields,
            },
        )

        self._results.append(result)
        return result


# =============================================================================
# Batch Verification Functions
# =============================================================================

def verify_all_products_have_name(product_ids: List[UUID]) -> Dict[str, bool]:
    """
    Verify all products have the 'name' field populated.

    Args:
        product_ids: List of product UUIDs to verify

    Returns:
        Dict mapping check names to pass/fail status
    """
    from crawler.models import DiscoveredProduct

    verifier = DataVerifier()
    results = {}

    for product_id in product_ids:
        try:
            product = DiscoveredProduct.objects.get(pk=product_id)
            product_data = {"name": product.name, "brand": product.brand}
            result = verifier.verify_product_required_fields(
                product_data,
                required_fields={"name"},
            )
            results[result.check_name] = result.passed
        except DiscoveredProduct.DoesNotExist:
            results[f"product_required_fields:{product_id}"] = False

    return results


def verify_all_products_have_palate_flavors(product_ids: List[UUID]) -> Dict[str, bool]:
    """
    Verify all products have palate_flavors populated.

    Args:
        product_ids: List of product UUIDs to verify

    Returns:
        Dict mapping check names to pass/fail status
    """
    from crawler.models import DiscoveredProduct

    verifier = DataVerifier()
    results = {}

    for product_id in product_ids:
        try:
            product = DiscoveredProduct.objects.get(pk=product_id)
            product_data = {
                "name": product.name,
                "palate_flavors": product.palate_flavors,
            }
            result = verifier.verify_palate_flavors_populated(product_data)
            results[result.check_name] = result.passed
        except DiscoveredProduct.DoesNotExist:
            results[f"palate_flavors:{product_id}"] = False

    return results


def verify_enriched_products_have_multiple_sources(product_ids: List[UUID]) -> Dict[str, bool]:
    """
    Verify enriched products have multiple source records.

    Args:
        product_ids: List of product UUIDs to verify

    Returns:
        Dict mapping check names to pass/fail status
    """
    verifier = DataVerifier()
    results = {}

    for product_id in product_ids:
        result = verifier.verify_source_tracking_exists(product_id, min_sources=2)
        results[result.check_name] = result.passed

    return results


def verify_competition_awards(
    product_ids: List[UUID],
    competition: str,
    year: int,
) -> Dict[str, bool]:
    """
    Verify products have award records for a specific competition.

    Args:
        product_ids: List of product UUIDs to verify
        competition: Competition name to verify
        year: Year to verify

    Returns:
        Dict mapping check names to pass/fail status
    """
    verifier = DataVerifier()
    results = {}

    for product_id in product_ids:
        result = verifier.verify_award_records(
            product_id,
            expected_competition=competition,
            expected_year=year,
        )
        results[result.check_name] = result.passed

    return results
