"""
E2E Test: Wayback Machine Archival Flow (Flow 8)

Tests the Wayback Machine archival pipeline for all CrawledSource records
created in previous flows.

This test:
1. Queries CrawledSource records from the test run
2. Submits each source URL to Wayback Machine via WaybackService
3. Waits for confirmation and stores archive URL
4. Updates wayback_status, wayback_url, and wayback_saved_at fields
5. Verifies all archive URLs are valid and accessible

Spec Reference: specs/E2E_TEST_SPECIFICATION_V2.md - Flow 8
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID

import httpx
import pytest
from asgiref.sync import sync_to_async
from django.utils import timezone

from tests.e2e.utils.data_verifier import DataVerifier, VerificationResult

logger = logging.getLogger(__name__)


# =============================================================================
# Test Constants
# =============================================================================

# Rate limiting settings to avoid throttling from Wayback Machine
RATE_LIMIT_SECONDS = 3.0  # Delay between archive requests
MAX_RETRIES = 3  # Maximum retry attempts per URL
RETRY_BASE_DELAY = 2.0  # Base delay for exponential backoff
ARCHIVE_VERIFICATION_TIMEOUT = 30.0  # Timeout for verifying archive URLs


# =============================================================================
# Helper Functions
# =============================================================================


@sync_to_async
def get_test_run_sources(
    test_run_tracker: "TestRunTracker",
    min_created_at: Optional[datetime] = None,
) -> List["CrawledSource"]:
    """
    Get CrawledSource records created during the test run.

    Args:
        test_run_tracker: Test run tracker with created source IDs
        min_created_at: Optional minimum creation timestamp

    Returns:
        List of CrawledSource records
    """
    from crawler.models import CrawledSource

    # If we have tracked source IDs, use those
    if test_run_tracker.created_sources:
        sources = CrawledSource.objects.filter(
            id__in=test_run_tracker.created_sources
        ).order_by("crawled_at")
        logger.info(
            f"Found {sources.count()} CrawledSource records from test run tracker"
        )
        return list(sources)

    # Fallback: query by timestamp
    if min_created_at is None:
        # Default to sources created in the last 24 hours
        min_created_at = timezone.now() - timedelta(hours=24)

    sources = CrawledSource.objects.filter(
        crawled_at__gte=min_created_at
    ).order_by("crawled_at")
    logger.info(
        f"Found {sources.count()} CrawledSource records since {min_created_at}"
    )
    return list(sources)


def get_sources_needing_archival(sources: List["CrawledSource"]) -> List["CrawledSource"]:
    """
    Filter sources that need Wayback archival.

    Args:
        sources: List of CrawledSource records

    Returns:
        List of sources with pending or failed wayback_status
    """
    from crawler.models import WaybackStatusChoices

    pending_sources = [
        s for s in sources
        if s.wayback_status in [
            WaybackStatusChoices.PENDING,
            WaybackStatusChoices.FAILED,
        ]
    ]
    logger.info(f"Found {len(pending_sources)} sources needing archival")
    return pending_sources


async def verify_archive_url_accessible(
    wayback_url: str,
    timeout: float = ARCHIVE_VERIFICATION_TIMEOUT,
) -> Dict[str, Any]:
    """
    Verify that a Wayback Machine archive URL is accessible.

    Args:
        wayback_url: The Wayback Machine archive URL to verify
        timeout: Request timeout in seconds

    Returns:
        Dict with verification results
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.head(
                wayback_url,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (compatible; SpiritswiseCrawler/2.0)"
                }
            )

            is_accessible = response.status_code in [200, 301, 302, 304]

            return {
                "accessible": is_accessible,
                "status_code": response.status_code,
                "url": wayback_url,
                "error": None,
            }

    except httpx.TimeoutException:
        return {
            "accessible": False,
            "status_code": None,
            "url": wayback_url,
            "error": "Timeout while verifying archive URL",
        }
    except httpx.RequestError as e:
        return {
            "accessible": False,
            "status_code": None,
            "url": wayback_url,
            "error": str(e),
        }


# =============================================================================
# Test Class
# =============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
class TestWaybackArchivalFlow:
    """
    E2E test for Wayback Machine Archival Flow.

    Archives all CrawledSource records from previous flows to the
    Wayback Machine and verifies the archival was successful.
    """

    @pytest.fixture(autouse=True)
    def setup(self, db):
        """Setup test dependencies."""
        self.verifier = DataVerifier()
        self.archived_sources: List[UUID] = []
        self.failed_sources: List[UUID] = []
        self.archival_results: List[Dict[str, Any]] = []

    async def test_wayback_archival_flow(
        self,
        wayback_service,
        test_run_tracker,
        report_collector,
    ):
        """
        Main test: Archive all CrawledSource records to Wayback Machine.

        Steps:
        1. Query CrawledSource records from this test run
        2. Filter sources needing archival (pending or failed status)
        3. Submit each source URL to Wayback Machine
        4. Wait for confirmation and update records
        5. Verify all archive URLs are accessible
        6. Track results (NO data deletion)
        """
        start_time = time.time()

        logger.info("=" * 60)
        logger.info("Starting Wayback Machine Archival Flow E2E Test")
        logger.info("=" * 60)

        # Get CrawledSource records from the test run
        sources = await get_test_run_sources(test_run_tracker)

        if not sources:
            logger.warning("No CrawledSource records found for archival")
            pytest.skip("No CrawledSource records found for archival")

        # Filter sources needing archival
        pending_sources = get_sources_needing_archival(sources)

        if not pending_sources:
            logger.info("All sources already archived, verifying existing archives")
            await self._verify_existing_archives(sources, report_collector)
            return

        logger.info(f"Archiving {len(pending_sources)} sources to Wayback Machine")

        # Archive each source with rate limiting
        for i, source in enumerate(pending_sources):
            logger.info(f"Archiving source {i + 1}/{len(pending_sources)}: {source.url[:80]}...")

            result = await self._archive_source_with_retry(
                source,
                wayback_service,
                test_run_tracker,
            )

            self.archival_results.append(result)

            # Record in report collector
            report_collector.add_source({
                "id": str(source.id),
                "url": source.url,
                "wayback_url": result.get("wayback_url"),
                "wayback_status": result.get("status"),
                "archival_success": result.get("success"),
            })

            # Rate limiting between requests
            if i < len(pending_sources) - 1:
                logger.debug(f"Rate limiting: waiting {RATE_LIMIT_SECONDS}s...")
                await asyncio.sleep(RATE_LIMIT_SECONDS)

        # Verify all archived sources
        await self._verify_all_archives(report_collector)

        # Record flow result
        duration = time.time() - start_time
        successful_count = len(self.archived_sources)
        failed_count = len(self.failed_sources)

        test_run_tracker.record_flow_result(
            flow_name="Wayback Archival",
            success=failed_count == 0,
            products_created=0,
            duration_seconds=duration,
            details={
                "total_sources": len(pending_sources),
                "successful": successful_count,
                "failed": failed_count,
                "archived_source_ids": [str(s) for s in self.archived_sources],
                "failed_source_ids": [str(s) for s in self.failed_sources],
            }
        )

        test_run_tracker.record_api_call("wayback", len(pending_sources))
        report_collector.record_flow_duration("Wayback Archival", duration)

        logger.info("=" * 60)
        logger.info(f"Wayback Archival Flow completed in {duration:.1f}s")
        logger.info(f"Successfully archived: {successful_count}")
        logger.info(f"Failed to archive: {failed_count}")
        logger.info("=" * 60)

        # Assert at least some sources were archived successfully
        assert successful_count > 0 or len(pending_sources) == 0, (
            f"Failed to archive any sources. {failed_count} failures."
        )

    async def _archive_source_with_retry(
        self,
        source: "CrawledSource",
        wayback_service,
        test_run_tracker,
    ) -> Dict[str, Any]:
        """
        Archive a single source with retry logic.

        Args:
            source: CrawledSource to archive
            wayback_service: WaybackService instance
            test_run_tracker: Test run tracker

        Returns:
            Dict with archival result
        """
        from crawler.models import WaybackStatusChoices

        # Use the service's archive_with_retry method
        result = await sync_to_async(wayback_service.archive_with_retry)(
            crawled_source=source,
            max_retries=MAX_RETRIES,
            base_delay=RETRY_BASE_DELAY,
        )

        # Refresh from database to get updated values
        await sync_to_async(source.refresh_from_db)()

        if result["success"]:
            self.archived_sources.append(source.id)
            logger.info(
                f"Successfully archived {source.url[:50]}... -> {result.get('wayback_url', 'N/A')[:60]}..."
            )
        else:
            self.failed_sources.append(source.id)
            logger.warning(
                f"Failed to archive {source.url[:50]}...: {result.get('error', 'Unknown error')}"
            )
            test_run_tracker.record_error(
                flow="Wayback Archival",
                error=result.get("error", "Unknown error"),
                context={"source_id": str(source.id), "url": source.url},
            )

        return {
            "source_id": str(source.id),
            "url": source.url,
            "success": result["success"],
            "wayback_url": source.wayback_url,
            "status": source.wayback_status,
            "saved_at": source.wayback_saved_at.isoformat() if source.wayback_saved_at else None,
            "error": result.get("error"),
        }

    async def _verify_all_archives(self, report_collector):
        """
        Verify all archived sources have accessible archive URLs.

        Args:
            report_collector: Report data collector
        """
        from crawler.models import CrawledSource

        logger.info("=" * 40)
        logger.info("Verifying archived sources")
        logger.info("=" * 40)

        for source_id in self.archived_sources:
            source = await sync_to_async(CrawledSource.objects.get)(pk=source_id)

            # Verify wayback fields are populated
            result = self.verifier.verify_wayback_archival(source_id)
            report_collector.record_verification(
                f"wayback_archival:{source_id}",
                result.passed,
            )

            if not result.passed:
                logger.warning(f"Verification failed for {source_id}: {result.message}")
                continue

            # Verify the archive URL is accessible
            if source.wayback_url:
                verification = await verify_archive_url_accessible(source.wayback_url)
                is_accessible = verification["accessible"]

                report_collector.record_verification(
                    f"wayback_accessible:{source_id}",
                    is_accessible,
                )

                if is_accessible:
                    logger.info(f"Archive URL accessible: {source.wayback_url[:60]}...")
                else:
                    logger.warning(
                        f"Archive URL not accessible: {source.wayback_url[:60]}... "
                        f"(status={verification.get('status_code')}, error={verification.get('error')})"
                    )

        # Summary
        passed = self.verifier.get_passed_count()
        failed = self.verifier.get_failed_count()
        total = passed + failed

        logger.info(f"Archive verification complete: {passed}/{total} checks passed")

    async def _verify_existing_archives(self, sources, report_collector):
        """
        Verify existing archive URLs are accessible.

        Called when all sources are already archived.

        Args:
            sources: List of CrawledSource records
            report_collector: Report data collector
        """
        from crawler.models import WaybackStatusChoices

        logger.info("Verifying existing Wayback archives...")

        saved_sources = [
            s for s in sources
            if s.wayback_status == WaybackStatusChoices.SAVED and s.wayback_url
        ]

        for source in saved_sources[:10]:  # Limit verification to avoid too many requests
            # Wrap sync DB call in sync_to_async
            result = await sync_to_async(self.verifier.verify_wayback_archival)(source.id)
            report_collector.record_verification(
                f"wayback_existing:{source.id}",
                result.passed,
            )

            if source.wayback_url:
                verification = await verify_archive_url_accessible(source.wayback_url)
                report_collector.record_verification(
                    f"wayback_accessible:{source.id}",
                    verification["accessible"],
                )

        logger.info(f"Verified {len(saved_sources[:10])} existing archives")


# =============================================================================
# Standalone Test Functions
# =============================================================================


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_wayback_service_available():
    """Verify WaybackService is available and properly configured."""
    from crawler.services.wayback_service import WaybackService

    service = WaybackService()
    assert service is not None, "WaybackService not available"
    assert hasattr(service, "archive_url"), "Missing archive_url method"
    assert hasattr(service, "archive_with_retry"), "Missing archive_with_retry method"
    assert hasattr(service, "archive_batch"), "Missing archive_batch method"
    assert hasattr(service, "mark_failed"), "Missing mark_failed method"

    logger.info("WaybackService is available and configured")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_wayback_service_cleanup_eligibility():
    """Test WaybackService cleanup eligibility check."""
    from crawler.services.wayback_service import WaybackService

    service = WaybackService()

    # Test cleanup eligibility
    assert service.is_cleanup_eligible("processed", "saved") is True
    assert service.is_cleanup_eligible("pending", "saved") is False
    assert service.is_cleanup_eligible("processed", "pending") is False
    assert service.is_cleanup_eligible("processed", "failed") is False

    logger.info("WaybackService cleanup eligibility check works correctly")


@pytest.mark.e2e
def test_wayback_status_choices(db):
    """Verify WaybackStatusChoices are properly defined."""
    from crawler.models import WaybackStatusChoices

    # Check all expected choices exist
    assert WaybackStatusChoices.PENDING == "pending"
    assert WaybackStatusChoices.SAVED == "saved"
    assert WaybackStatusChoices.FAILED == "failed"
    assert WaybackStatusChoices.NOT_APPLICABLE == "not_applicable"

    logger.info("WaybackStatusChoices are properly defined")


@pytest.mark.e2e
def test_crawled_source_wayback_fields(db, source_factory):
    """Verify CrawledSource has all required Wayback fields."""
    source = source_factory(
        url="https://example.com/test-wayback-fields",
        title="Test Wayback Fields",
    )

    # Check Wayback fields exist
    assert hasattr(source, "wayback_url"), "Missing wayback_url field"
    assert hasattr(source, "wayback_status"), "Missing wayback_status field"
    assert hasattr(source, "wayback_saved_at"), "Missing wayback_saved_at field"

    # Check default values
    from crawler.models import WaybackStatusChoices
    assert source.wayback_status == WaybackStatusChoices.PENDING
    assert source.wayback_url is None
    assert source.wayback_saved_at is None

    logger.info("CrawledSource has all required Wayback fields")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_archive_url_verification():
    """Test the archive URL accessibility verification function."""
    # Test with a known Wayback Machine URL
    # Using a well-known archived page
    test_url = "https://web.archive.org/web/20240101000000/https://example.com/"

    result = await verify_archive_url_accessible(test_url, timeout=15.0)

    # The result should have the expected structure
    assert "accessible" in result
    assert "status_code" in result
    assert "url" in result
    assert "error" in result
    assert result["url"] == test_url

    logger.info(f"Archive URL verification test completed: accessible={result['accessible']}")


@pytest.mark.e2e
@pytest.mark.asyncio
async def test_batch_archival_respects_rate_limiting(wayback_service):
    """Verify batch archival respects rate limiting."""
    # This is a documentation test to verify the rate limiting parameter
    assert hasattr(wayback_service, "archive_batch"), "Missing archive_batch method"

    # Check the method signature includes rate_limit_seconds
    import inspect
    sig = inspect.signature(wayback_service.archive_batch)
    assert "rate_limit_seconds" in sig.parameters, (
        "archive_batch should have rate_limit_seconds parameter"
    )

    # Verify default rate limit is reasonable (>= 2 seconds)
    default_rate = sig.parameters["rate_limit_seconds"].default
    assert default_rate >= 2.0, f"Rate limit too low: {default_rate}s"

    logger.info(f"Batch archival rate limiting configured: {default_rate}s")
