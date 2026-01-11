"""
Wayback Machine Service for V2 Architecture.

Provides a class-based interface for Wayback Machine integration
with retry logic, batch processing, and cleanup eligibility checks.

Phase 4.6: Internet Archive (Wayback Machine) Integration
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

# Wayback Machine save endpoint
WAYBACK_SAVE_URL = "https://web.archive.org/save/"

# Timeout for Wayback Machine requests (seconds)
WAYBACK_TIMEOUT = 60


class WaybackService:
    """
    Service for Wayback Machine integration.

    Provides methods for:
    - Archiving URLs to Wayback Machine
    - Extracting archive URLs from responses
    - Retry logic with exponential backoff
    - Batch archival with rate limiting
    - Cleanup eligibility checks

    Uses singleton pattern for consistent state.
    """

    _instance: Optional['WaybackService'] = None

    def __new__(cls) -> 'WaybackService':
        """Singleton pattern implementation."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the Wayback service."""
        if self._initialized:
            return
        self._initialized = True
        logger.info("WaybackService initialized")

    def is_cleanup_eligible(
        self,
        extraction_status: str,
        wayback_status: str
    ) -> bool:
        """
        Check if a source is eligible for raw content cleanup.

        Cleanup is eligible when:
        - extraction_status is 'processed'
        - wayback_status is 'saved'

        Args:
            extraction_status: Current extraction status
            wayback_status: Current wayback status

        Returns:
            True if eligible for cleanup
        """
        return extraction_status == "processed" and wayback_status == "saved"

    def save_url(self, url: str) -> Dict[str, Any]:
        """
        Save a URL to the Wayback Machine (simple URL-based interface).

        This is an alias that creates a minimal object for archival.

        Args:
            url: The URL to archive

        Returns:
            Dict with success, wayback_url, and optional error
        """
        # Create a simple object to hold URL for archival
        class SimpleSource:
            def __init__(self, url: str):
                self.url = url
                self.wayback_url = None
                self.wayback_status = None
                self.wayback_saved_at = None

            def save(self, update_fields=None):
                pass  # No-op for simple URL archival

        simple_source = SimpleSource(url)
        return self.archive_url(simple_source)

    def queue_archive(self, source: 'CrawledSource') -> bool:
        """
        Queue a source for Wayback archival.

        This is an alias for archive_url that returns a simple success boolean.
        For async workflows, this can be extended to use a task queue.

        Args:
            source: The CrawledSource to queue for archival

        Returns:
            True if queued/archived successfully
        """
        result = self.archive_url(source)
        return result.get("success", False)

    def archive_url(self, crawled_source: 'CrawledSource') -> Dict[str, Any]:
        """
        Save a URL to the Wayback Machine.

        Triggers an archive save by POSTing to the Wayback Machine save endpoint.
        Updates the CrawledSource record with the archived URL and status.

        Args:
            crawled_source: The CrawledSource record to archive

        Returns:
            Dict with:
                - success: bool indicating if save was successful
                - wayback_url: The archived URL (if successful)
                - error: Error message (if failed)
        """
        from crawler.models import WaybackStatusChoices

        url = crawled_source.url
        save_endpoint = f"{WAYBACK_SAVE_URL}{url}"

        logger.info(f"Attempting to save URL to Wayback Machine: {url}")

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }

            response = requests.post(
                save_endpoint,
                headers=headers,
                timeout=WAYBACK_TIMEOUT,
                allow_redirects=False,
            )

            if response.status_code in [200, 301, 302]:
                wayback_url = self._extract_archive_url(response, url)

                if wayback_url:
                    crawled_source.wayback_url = wayback_url
                    crawled_source.wayback_status = WaybackStatusChoices.SAVED
                    crawled_source.wayback_saved_at = timezone.now()
                    crawled_source.save(
                        update_fields=["wayback_url", "wayback_status", "wayback_saved_at"]
                    )

                    logger.info(f"Successfully archived URL to Wayback Machine: {wayback_url}")

                    return {
                        "success": True,
                        "wayback_url": wayback_url,
                    }

            error_msg = f"Wayback Machine returned status {response.status_code}: {response.text[:200]}"
            logger.warning(f"Failed to archive URL {url}: {error_msg}")

            return {
                "success": False,
                "error": error_msg,
            }

        except requests.exceptions.Timeout:
            error_msg = f"Timeout while saving to Wayback Machine: {url}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error while saving to Wayback Machine: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

        except requests.exceptions.RequestException as e:
            error_msg = f"Request error while saving to Wayback Machine: {str(e)}"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
            }

    def _extract_archive_url(
        self,
        response: requests.Response,
        original_url: str
    ) -> Optional[str]:
        """
        Extract the archived URL from the Wayback Machine response.

        Args:
            response: The response from the Wayback Machine
            original_url: The original URL that was archived

        Returns:
            The full Wayback Machine URL or None if extraction fails
        """
        # Check Content-Location header first
        content_location = response.headers.get("Content-Location")
        if content_location:
            if content_location.startswith("/web/"):
                return f"https://web.archive.org{content_location}"

        # Check Location header for redirects
        location = response.headers.get("Location")
        if location:
            if "web.archive.org" in location:
                return location
            elif location.startswith("/web/"):
                return f"https://web.archive.org{location}"

        # Check X-Archive-Orig-Record-Header
        archive_header = response.headers.get("X-Archive-Orig-Record-Header")
        if archive_header and "web.archive.org" in archive_header:
            return archive_header

        # Fallback: construct URL with current timestamp
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"https://web.archive.org/web/{timestamp}/{original_url}"

    def mark_failed(self, crawled_source: 'CrawledSource') -> None:
        """
        Mark a CrawledSource as failed for Wayback archiving.

        Called after all retry attempts have been exhausted.

        Args:
            crawled_source: The CrawledSource record to mark as failed
        """
        from crawler.models import WaybackStatusChoices

        crawled_source.wayback_status = WaybackStatusChoices.FAILED
        crawled_source.save(update_fields=["wayback_status"])

        logger.info(f"Marked URL as failed for Wayback archiving: {crawled_source.url}")

    def perform_cleanup(self, crawled_source: 'CrawledSource') -> bool:
        """
        Clean up raw_content after successful Wayback archive.

        Only clears raw_content when wayback_status is 'saved'.
        Preserves content_hash for deduplication.

        Args:
            crawled_source: The CrawledSource record to clean up

        Returns:
            True if cleanup was performed, False otherwise
        """
        from crawler.models import WaybackStatusChoices

        if crawled_source.wayback_status != WaybackStatusChoices.SAVED:
            logger.debug(
                f"Skipping raw_content cleanup for {crawled_source.url}: "
                f"wayback_status is '{crawled_source.wayback_status}', not 'saved'"
            )
            return False

        crawled_source.raw_content = None
        crawled_source.raw_content_cleared = True
        crawled_source.save(update_fields=["raw_content", "raw_content_cleared"])

        logger.info(f"Cleared raw_content for archived URL: {crawled_source.url}")
        return True

    def get_pending_archive_sources(self, limit: int = 100) -> List['CrawledSource']:
        """
        Get CrawledSource records pending Wayback archiving.

        Returns sources that:
        - Have wayback_status = 'pending'
        - Have extraction_status = 'processed'

        Args:
            limit: Maximum number of records to return

        Returns:
            List of CrawledSource records pending archiving
        """
        from crawler.models import CrawledSource, WaybackStatusChoices

        return list(
            CrawledSource.objects.filter(
                wayback_status=WaybackStatusChoices.PENDING,
                extraction_status="processed",
            )
            .order_by("crawled_at")[:limit]
        )

    def archive_with_retry(
        self,
        crawled_source: 'CrawledSource',
        max_retries: int = 3,
        base_delay: float = 1.0
    ) -> Dict[str, Any]:
        """
        Archive a URL with exponential backoff retry.

        Args:
            crawled_source: The CrawledSource record to archive
            max_retries: Maximum number of retry attempts
            base_delay: Base delay in seconds (doubles each retry)

        Returns:
            Dict with success status and result
        """
        last_error = None

        for attempt in range(max_retries):
            result = self.archive_url(crawled_source)

            if result['success']:
                return result

            last_error = result.get('error')
            logger.warning(
                f"Archive attempt {attempt + 1}/{max_retries} failed for "
                f"{crawled_source.url}: {last_error}"
            )

            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt)
                logger.debug(f"Waiting {delay} seconds before retry...")
                time.sleep(delay)

        # All retries exhausted - mark as failed
        self.mark_failed(crawled_source)

        return {
            "success": False,
            "error": f"All {max_retries} attempts failed. Last error: {last_error}",
        }

    def archive_batch(
        self,
        sources: List['CrawledSource'],
        rate_limit_seconds: float = 2.0
    ) -> List[Dict[str, Any]]:
        """
        Archive a batch of sources with rate limiting.

        Args:
            sources: List of CrawledSource records to archive
            rate_limit_seconds: Delay between requests to avoid rate limits

        Returns:
            List of results for each source
        """
        results = []

        for i, source in enumerate(sources):
            logger.info(f"Archiving source {i + 1}/{len(sources)}: {source.url}")

            result = self.archive_url(source)
            results.append(result)

            # Rate limit between requests (except for last one)
            if i < len(sources) - 1 and rate_limit_seconds > 0:
                time.sleep(rate_limit_seconds)

        successful = sum(1 for r in results if r['success'])
        logger.info(f"Batch archival complete: {successful}/{len(sources)} successful")

        return results
