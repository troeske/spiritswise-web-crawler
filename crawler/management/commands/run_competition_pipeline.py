"""
Management command to run the competition/award discovery pipeline.

Usage:
    python manage.py run_competition_pipeline --competition iwsc --year 2024
    python manage.py run_competition_pipeline --all --year 2024
    python manage.py run_competition_pipeline --enrich --limit 50
"""

import asyncio
from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from crawler.models import (
    CrawlerSource,
    CrawlJob,
    DiscoveredProduct,
    DiscoveredProductStatus,
    SourceCategory,
)
from crawler.services.competition_orchestrator import (
    CompetitionOrchestrator,
    ensure_competition_sources_exist,
    COMPETITION_SOURCES,
)
from crawler.fetchers.smart_router import SmartRouter


class Command(BaseCommand):
    help = "Run the competition/award discovery pipeline"

    def add_arguments(self, parser):
        parser.add_argument(
            "--competition",
            type=str,
            help="Competition key to run (iwsc, sfwsc, wwa, decanter-wwa)",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=datetime.now().year,
            help="Competition year (default: current year)",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Run discovery for all competition sources",
        )
        parser.add_argument(
            "--enrich",
            action="store_true",
            help="Run enrichment searches for skeleton products",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum skeletons to process for enrichment (default: 50)",
        )
        parser.add_argument(
            "--process-queue",
            action="store_true",
            help="Process URLs from the enrichment queue",
        )
        parser.add_argument(
            "--max-urls",
            type=int,
            default=100,
            help="Maximum URLs to process from enrichment queue (default: 100)",
        )
        parser.add_argument(
            "--setup",
            action="store_true",
            help="Set up competition sources in database",
        )
        parser.add_argument(
            "--stats",
            action="store_true",
            help="Show skeleton product statistics",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without actually doing it",
        )

    def handle(self, *args, **options):
        # Setup competition sources
        if options["setup"]:
            self._setup_competition_sources()
            return

        # Show statistics
        if options["stats"]:
            self._show_statistics()
            return

        # Run enrichment searches
        if options["enrich"]:
            self._run_enrichment(
                limit=options["limit"],
                dry_run=options["dry_run"],
            )
            return

        # Process enrichment queue
        if options["process_queue"]:
            self._process_enrichment_queue(
                max_urls=options["max_urls"],
                dry_run=options["dry_run"],
            )
            return

        # Run competition discovery
        if options["all"]:
            self._run_all_competitions(
                year=options["year"],
                dry_run=options["dry_run"],
            )
        elif options["competition"]:
            self._run_single_competition(
                competition_key=options["competition"],
                year=options["year"],
                dry_run=options["dry_run"],
            )
        else:
            self.stdout.write(self.style.WARNING(
                "Please specify --competition, --all, --enrich, --process-queue, --setup, or --stats"
            ))
            self.stdout.write("\nAvailable competitions:")
            for slug, data in [(s["slug"], s) for s in COMPETITION_SOURCES]:
                self.stdout.write(f"  {slug}: {data['name']}")

    def _setup_competition_sources(self):
        """Set up competition sources in the database."""
        self.stdout.write("Setting up competition sources...")
        created = ensure_competition_sources_exist()
        self.stdout.write(self.style.SUCCESS(f"Created {created} competition sources"))

        # List all competition sources
        sources = CrawlerSource.objects.filter(category=SourceCategory.COMPETITION)
        self.stdout.write(f"\nCompetition sources in database ({sources.count()}):")
        for source in sources:
            status = "active" if source.is_active else "inactive"
            self.stdout.write(f"  [{status}] {source.slug}: {source.name}")

    def _show_statistics(self):
        """Show skeleton product statistics."""
        orchestrator = CompetitionOrchestrator()
        stats = orchestrator.get_skeleton_statistics()

        self.stdout.write("\nSkeleton Product Statistics:")
        self.stdout.write("=" * 50)
        self.stdout.write(f"  Total skeletons: {stats['total_skeletons']}")
        self.stdout.write(f"  Awaiting enrichment: {stats['awaiting_enrichment']}")
        self.stdout.write(f"  Already enriched: {stats['enriched']}")

        if stats["by_competition"]:
            self.stdout.write("\nBy competition:")
            for comp in stats["by_competition"]:
                competition = comp.get("awards__0__competition") or "Unknown"
                count = comp["count"]
                self.stdout.write(f"  {competition}: {count}")

        # Count skeletons by status
        status_counts = {}
        for status in DiscoveredProductStatus.choices:
            count = DiscoveredProduct.objects.filter(status=status[0]).count()
            if count > 0:
                status_counts[status[1]] = count

        if status_counts:
            self.stdout.write("\nAll products by status:")
            for status, count in status_counts.items():
                self.stdout.write(f"  {status}: {count}")

    def _run_single_competition(self, competition_key: str, year: int, dry_run: bool):
        """Run discovery for a single competition."""
        # Find source
        try:
            source = CrawlerSource.objects.get(slug=competition_key)
        except CrawlerSource.DoesNotExist:
            # Try to match by partial name
            sources = CrawlerSource.objects.filter(
                category=SourceCategory.COMPETITION,
                slug__icontains=competition_key,
            )
            if sources.count() == 1:
                source = sources.first()
            elif sources.count() > 1:
                self.stdout.write(self.style.ERROR(f"Multiple sources match '{competition_key}':"))
                for s in sources:
                    self.stdout.write(f"  {s.slug}")
                return
            else:
                raise CommandError(f"Competition source '{competition_key}' not found")

        self.stdout.write(f"Running discovery for {source.name}, year {year}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))
            self.stdout.write(f"  Would fetch: {source.base_url}")
            return

        # Create crawl job
        job = CrawlJob.objects.create(source=source)
        job.start()

        # Build URL
        competition_url = source.base_url
        if "{year}" in competition_url:
            competition_url = competition_url.format(year=year)
        elif not competition_url.endswith(str(year)):
            if competition_url.endswith("/"):
                competition_url = f"{competition_url}{year}"
            else:
                competition_url = f"{competition_url}/{year}"

        self.stdout.write(f"Fetching URL: {competition_url}")

        # Run async operations
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Fetch competition page
            router = SmartRouter()
            fetch_result = loop.run_until_complete(
                router.fetch(competition_url, source=source, crawl_job=job)
            )

            if not fetch_result.success:
                self.stdout.write(self.style.ERROR(f"Failed to fetch: {fetch_result.error}"))
                job.complete(success=False, error_message=fetch_result.error)
                return

            self.stdout.write(self.style.SUCCESS(f"Fetched {len(fetch_result.content)} bytes"))

            # Run discovery
            orchestrator = CompetitionOrchestrator()
            result = loop.run_until_complete(
                orchestrator.run_competition_discovery(
                    competition_url=competition_url,
                    crawl_job=job,
                    html_content=fetch_result.content,
                    competition_key=competition_key,
                    year=year,
                )
            )

            loop.run_until_complete(router.close())

            # Update job
            job.pages_crawled = 1
            job.products_found = result.awards_found
            job.products_new = result.skeletons_created
            job.products_updated = result.skeletons_updated
            job.errors_count = len(result.errors)
            job.complete(success=result.success)

            # Report results
            self.stdout.write("\nResults:")
            self.stdout.write(f"  Awards found: {result.awards_found}")
            self.stdout.write(f"  Skeletons created: {result.skeletons_created}")
            self.stdout.write(f"  Skeletons updated: {result.skeletons_updated}")

            if result.errors:
                self.stdout.write(self.style.WARNING(f"  Errors: {len(result.errors)}"))
                for error in result.errors[:5]:
                    self.stdout.write(f"    - {error}")

            if result.success:
                self.stdout.write(self.style.SUCCESS("\nDiscovery completed successfully!"))
            else:
                self.stdout.write(self.style.ERROR("\nDiscovery completed with errors"))

        finally:
            loop.close()

    def _run_all_competitions(self, year: int, dry_run: bool):
        """Run discovery for all active competition sources."""
        sources = CrawlerSource.objects.filter(
            category=SourceCategory.COMPETITION,
            is_active=True,
        )

        if not sources.exists():
            self.stdout.write(self.style.WARNING(
                "No active competition sources found. Run --setup first."
            ))
            return

        self.stdout.write(f"Running discovery for {sources.count()} competition sources, year {year}")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))
            for source in sources:
                self.stdout.write(f"  Would process: {source.slug}")
            return

        total_awards = 0
        total_skeletons = 0

        for source in sources:
            self.stdout.write(f"\n--- {source.name} ---")
            try:
                self._run_single_competition(
                    competition_key=source.slug,
                    year=year,
                    dry_run=False,
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error: {e}"))

        self.stdout.write(self.style.SUCCESS(
            f"\nAll competitions processed!"
        ))

    def _run_enrichment(self, limit: int, dry_run: bool):
        """Run enrichment searches for skeleton products."""
        orchestrator = CompetitionOrchestrator()

        pending_count = orchestrator.get_pending_skeletons_count()
        self.stdout.write(f"Found {pending_count} skeleton products awaiting enrichment")

        if pending_count == 0:
            self.stdout.write(self.style.SUCCESS("No skeletons need enrichment"))
            return

        actual_limit = min(limit, pending_count)
        self.stdout.write(f"Processing up to {actual_limit} skeletons")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))
            # Show which skeletons would be processed
            skeletons = orchestrator.skeleton_manager.get_unenriched_skeletons(limit=actual_limit)
            for skeleton in skeletons:
                name = skeleton.extracted_data.get("name", "Unknown")
                self.stdout.write(f"  Would enrich: {name}")
            return

        # Run async enrichment
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            result = loop.run_until_complete(
                orchestrator.process_skeletons_for_enrichment(limit=actual_limit)
            )

            self.stdout.write("\nEnrichment Results:")
            self.stdout.write(f"  Skeletons processed: {result.skeletons_processed}")
            self.stdout.write(f"  URLs discovered: {result.urls_discovered}")
            self.stdout.write(f"  URLs queued: {result.urls_queued}")

            if result.errors:
                self.stdout.write(self.style.WARNING(f"  Errors: {len(result.errors)}"))

            if result.success:
                self.stdout.write(self.style.SUCCESS("\nEnrichment completed successfully!"))
            else:
                self.stdout.write(self.style.ERROR("\nEnrichment completed with errors"))

        finally:
            loop.close()

    def _process_enrichment_queue(self, max_urls: int, dry_run: bool):
        """Process URLs from the enrichment queue."""
        from crawler.queue.url_frontier import get_url_frontier

        frontier = get_url_frontier()
        queue_size = frontier.get_queue_size("enrichment")

        self.stdout.write(f"Enrichment queue size: {queue_size}")

        if queue_size == 0:
            self.stdout.write(self.style.SUCCESS("Enrichment queue is empty"))
            return

        actual_max = min(max_urls, queue_size)
        self.stdout.write(f"Processing up to {actual_max} URLs")

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - no changes will be made"))
            # Peek at some URLs
            for _ in range(min(5, queue_size)):
                entry = frontier.peek_next_url("enrichment")
                if entry:
                    self.stdout.write(f"  Would process: {entry['url'][:60]}...")
            return

        # Import the task and run it directly
        from crawler.tasks import process_skeleton_enrichment_queue

        result = process_skeleton_enrichment_queue(max_urls=actual_max)

        if result.get("status") == "completed":
            metrics = result.get("metrics", {})
            self.stdout.write("\nProcessing Results:")
            self.stdout.write(f"  URLs processed: {metrics.get('urls_processed', 0)}")
            self.stdout.write(f"  Skeletons enriched: {metrics.get('skeletons_enriched', 0)}")
            self.stdout.write(f"  Errors: {metrics.get('errors', 0)}")
            self.stdout.write(self.style.SUCCESS("\nQueue processing completed!"))
        else:
            self.stdout.write(self.style.ERROR(f"Queue processing failed: {result.get('error')}"))
