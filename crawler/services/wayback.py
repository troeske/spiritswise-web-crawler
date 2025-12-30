"""
Wayback Machine Integration Service.

Task Group 31: Implements Wayback Machine integration for archiving crawled pages.

Features:
- POST to https://web.archive.org/save/{url} to trigger archive
- Parse response for archived URL (format: https://web.archive.org/web/{timestamp}/{url})
- Update CrawledSource.wayback_url and wayback_saved_at
- Update wayback_status to 'saved' or 'failed'
- Raw content cleanup utility after successful archive
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

import requests
from django.utils import timezone

from crawler.models import CrawledSource, WaybackStatusChoices

logger = logging.getLogger(__name__)

# Wayback Machine save endpoint
WAYBACK_SAVE_URL = "https://web.archive.org/save/"

# Timeout for Wayback Machine requests (seconds)
WAYBACK_TIMEOUT = 60


def save_to_wayback(crawled_source: CrawledSource) -> Dict[str, Any]:
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
    url = crawled_source.url
    save_endpoint = f"{WAYBACK_SAVE_URL}{url}"

    logger.info(f"Attempting to save URL to Wayback Machine: {url}")

    try:
        # POST to Wayback Machine save endpoint
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

        # Check for successful archive
        if response.status_code in [200, 301, 302]:
            # Extract archived URL from Content-Location header or construct it
            wayback_url = _extract_wayback_url(response, url)

            if wayback_url:
                # Update CrawledSource with success
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

        # Archive failed - log but don't update status to failed yet (allow retry)
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


def _extract_wayback_url(response: requests.Response, original_url: str) -> Optional[str]:
    """
    Extract the archived URL from the Wayback Machine response.

    The Wayback Machine returns the archived URL in the Content-Location header
    or as a redirect Location header.

    Args:
        response: The response from the Wayback Machine
        original_url: The original URL that was archived

    Returns:
        The full Wayback Machine URL or None if extraction fails
    """
    # Check Content-Location header first (common response format)
    content_location = response.headers.get("Content-Location")
    if content_location:
        # Content-Location usually starts with /web/timestamp/url
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

    # Last resort: construct URL with current timestamp
    # This is less reliable but provides a fallback
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    return f"https://web.archive.org/web/{timestamp}/{original_url}"


def mark_wayback_failed(crawled_source: CrawledSource) -> None:
    """
    Mark a CrawledSource as failed for Wayback archiving.

    Called after all retry attempts have been exhausted.

    Args:
        crawled_source: The CrawledSource record to mark as failed
    """
    crawled_source.wayback_status = WaybackStatusChoices.FAILED
    crawled_source.save(update_fields=["wayback_status"])

    logger.info(f"Marked URL as failed for Wayback archiving: {crawled_source.url}")


def cleanup_raw_content(crawled_source: CrawledSource) -> bool:
    """
    Clean up raw_content after successful Wayback archive.

    Only clears raw_content when wayback_status is 'saved'.
    Preserves content_hash for deduplication.

    Args:
        crawled_source: The CrawledSource record to clean up

    Returns:
        True if cleanup was performed, False otherwise
    """
    # Only cleanup if wayback_status is saved
    if crawled_source.wayback_status != WaybackStatusChoices.SAVED:
        logger.debug(
            f"Skipping raw_content cleanup for {crawled_source.url}: "
            f"wayback_status is '{crawled_source.wayback_status}', not 'saved'"
        )
        return False

    # Clear raw_content but keep content_hash for deduplication
    crawled_source.raw_content = None
    crawled_source.raw_content_cleared = True
    crawled_source.save(update_fields=["raw_content", "raw_content_cleared"])

    logger.info(f"Cleared raw_content for archived URL: {crawled_source.url}")
    return True


def get_pending_wayback_sources(limit: int = 100) -> list:
    """
    Get CrawledSource records pending Wayback archiving.

    Returns sources that:
    - Have wayback_status = 'pending'
    - Have extraction_status = 'processed' (already extracted)

    Args:
        limit: Maximum number of records to return

    Returns:
        List of CrawledSource records pending archiving
    """
    return list(
        CrawledSource.objects.filter(
            wayback_status=WaybackStatusChoices.PENDING,
            extraction_status="processed",
        )
        .order_by("crawled_at")[:limit]
    )
