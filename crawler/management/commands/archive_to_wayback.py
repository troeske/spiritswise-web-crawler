"""
Management command to archive pending CrawledSource URLs to Wayback Machine.

Phase 4.8: Wayback Archive Job

Usage:
    python manage.py archive_to_wayback
    python manage.py archive_to_wayback --dry-run
    python manage.py archive_to_wayback --batch-size=50 --rate-limit=2
"""

import logging
import time

from django.core.management.base import BaseCommand

from crawler.models import CrawledSource, WaybackStatusChoices
from crawler.services.wayback_service import WaybackService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Archive pending CrawledSource URLs to Wayback Machine."""

    help = 'Archive pending CrawledSource URLs to the Wayback Machine'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without actually archiving',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of URLs to process per batch (default: 50)',
        )
        parser.add_argument(
            '--rate-limit',
            type=float,
            default=2.0,
            help='Seconds to wait between archive requests (default: 2.0)',
        )
        parser.add_argument(
            '--max-retries',
            type=int,
            default=3,
            help='Maximum retry attempts per URL (default: 3)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Print verbose output for each URL',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        rate_limit = options['rate_limit']
        max_retries = options['max_retries']
        verbose = options['verbose']

        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode - no URLs will be archived'))

        # Get pending sources
        pending_sources = list(CrawledSource.objects.filter(
            wayback_status=WaybackStatusChoices.PENDING,
            extraction_status="processed",
        ).order_by('crawled_at')[:batch_size])

        total_count = len(pending_sources)

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No sources pending archive'))
            return

        self.stdout.write(f'Found {total_count} sources pending archive')

        wayback_service = WaybackService()
        success_count = 0
        failed_count = 0

        for i, source in enumerate(pending_sources):
            if verbose:
                self.stdout.write(f'  [{i + 1}/{total_count}] Archiving: {source.url}')

            if dry_run:
                success_count += 1
                continue

            # Archive with retry logic
            result = wayback_service.archive_with_retry(
                source,
                max_retries=max_retries
            )

            if result['success']:
                success_count += 1
                if verbose:
                    self.stdout.write(
                        self.style.SUCCESS(f'    Success: {result.get("wayback_url", "OK")}')
                    )
            else:
                failed_count += 1
                if verbose:
                    self.stdout.write(
                        self.style.ERROR(f'    Failed: {result.get("error", "Unknown error")}')
                    )

            # Rate limiting (except for last item)
            if i < total_count - 1 and rate_limit > 0:
                time.sleep(rate_limit)

        # Report results
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'Dry run: Would have archived {success_count} URLs')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully archived {success_count} URLs')
            )
            if failed_count > 0:
                self.stdout.write(
                    self.style.WARNING(f'Failed to archive {failed_count} URLs')
                )

        # Report remaining pending sources
        remaining = CrawledSource.objects.filter(
            wayback_status=WaybackStatusChoices.PENDING,
            extraction_status="processed",
        ).count()

        if remaining > 0:
            self.stdout.write(f'{remaining} URLs still pending archive')
