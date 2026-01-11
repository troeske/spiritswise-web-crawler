"""
Simple test to run DiscoveryOrchestrator with debug logging enabled.
"""
import os
import sys
import django
import logging

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

# Configure logging to show all DEBUG messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set discovery_orchestrator logger to DEBUG
orchestrator_logger = logging.getLogger('crawler.services.discovery_orchestrator')
orchestrator_logger.setLevel(logging.DEBUG)

from crawler.models import CrawlSchedule, ScheduleCategory
from crawler.services.discovery_orchestrator import DiscoveryOrchestrator


def run_test():
    print("=" * 70)
    print("Testing Discovery Orchestrator with Debug Logging")
    print("=" * 70)

    # Create or get a test schedule with search_terms as JSON list
    schedule, created = CrawlSchedule.objects.update_or_create(
        slug="debug-test-scotch",
        defaults={
            "name": "Debug Test - Best Scotch",
            "category": ScheduleCategory.DISCOVERY,
            "is_active": True,
            "max_results_per_term": 3,  # Limit to 3 results for quick test
            "search_terms": ["Best Scotch Whisky 2024"],  # JSON list of search terms
        }
    )
    print(f"Schedule: {schedule.name} (created={created})")
    print(f"Search terms: {schedule.search_terms}")

    # Run the orchestrator
    print("\n" + "=" * 70)
    print("Running Discovery Orchestrator...")
    print("=" * 70 + "\n")

    orchestrator = DiscoveryOrchestrator(schedule)
    job = orchestrator.run()

    print("\n" + "=" * 70)
    print("Discovery Job Results:")
    print("=" * 70)
    print(f"  Job ID: {job.id}")
    print(f"  Status: {job.status}")
    print(f"  Search terms processed: {job.search_terms_processed}/{job.search_terms_total}")
    print(f"  URLs found: {job.urls_found}")
    print(f"  URLs crawled: {job.urls_crawled}")
    print(f"  URLs skipped: {job.urls_skipped}")
    print(f"  Products new: {job.products_new}")
    print(f"  Products updated: {job.products_updated}")
    print(f"  Products duplicates: {job.products_duplicates}")
    print(f"  Products failed: {job.products_failed}")
    print(f"  SerpAPI calls: {job.serpapi_calls_used}")
    print(f"  ScrapingBee calls: {job.scrapingbee_calls_used}")
    print(f"  AI calls: {job.ai_calls_used}")
    print(f"  Errors: {job.error_count}")
    print("=" * 70)


if __name__ == "__main__":
    run_test()
