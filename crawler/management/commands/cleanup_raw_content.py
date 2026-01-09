"""
Management command to cleanup raw_content from eligible CrawledSource records.

Phase 4.7: Content Cleanup Job

Usage:
    python manage.py cleanup_raw_content
    python manage.py cleanup_raw_content --dry-run
    python manage.py cleanup_raw_content --batch-size=100
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from crawler.models import CrawledSource

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Cleanup raw_content from eligible CrawledSource records."""

    help = 'Cleanup raw_content from CrawledSource records that are eligible for cleanup'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run in dry-run mode without actually deleting content',
        )
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Number of sources to process per batch (default: 100)',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Print verbose output for each source',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        batch_size = options['batch_size']
        verbose = options['verbose']

        if dry_run:
            self.stdout.write(self.style.WARNING('Running in dry-run mode - no content will be deleted'))

        # Query for eligible sources
        eligible_sources = CrawledSource.objects.filter(
            cleanup_eligible=True,
            raw_content_cleared=False,
            raw_content__isnull=False
        ).order_by('crawled_at')[:batch_size]

        total_count = eligible_sources.count()

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS('No sources eligible for cleanup'))
            return

        self.stdout.write(f'Found {total_count} sources eligible for cleanup')

        cleaned_count = 0

        for source in eligible_sources:
            if verbose:
                self.stdout.write(f'  Processing: {source.url}')

            if not dry_run:
                with transaction.atomic():
                    source.raw_content = None
                    source.raw_content_cleared = True
                    source.save(update_fields=['raw_content', 'raw_content_cleared'])

            cleaned_count += 1

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f'Dry run: Would have cleaned up {cleaned_count} sources')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f'Successfully cleaned up {cleaned_count} sources')
            )

        # Report remaining eligible sources
        remaining = CrawledSource.objects.filter(
            cleanup_eligible=True,
            raw_content_cleared=False,
            raw_content__isnull=False
        ).count()

        if remaining > 0:
            self.stdout.write(f'{remaining} sources still pending cleanup')
