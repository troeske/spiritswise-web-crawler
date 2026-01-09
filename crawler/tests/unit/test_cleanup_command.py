"""
Unit tests for cleanup_raw_content management command.

Tests Phase 4.7: Content Cleanup Job
"""

import pytest
from io import StringIO
from unittest.mock import Mock, patch, MagicMock
from django.core.management import call_command


class TestCleanupRawContentCommand:
    """Tests for cleanup_raw_content management command."""

    @pytest.mark.django_db
    def test_command_exists(self):
        """Test cleanup_raw_content command can be called."""
        out = StringIO()
        call_command('cleanup_raw_content', '--dry-run', stdout=out)
        output = out.getvalue()
        assert 'cleanup' in output.lower() or 'dry' in output.lower()

    @pytest.mark.django_db
    def test_dry_run_does_not_delete(self):
        """Test dry run mode doesn't actually delete content."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        # Create eligible source
        source = CrawledSource.objects.create(
            url="https://example.com/dry-run-test",
            title="Dry Run Test",
            source_type="review_article",
            raw_content="<html>content</html>",
            raw_content_cleared=False,
            cleanup_eligible=True,
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.SAVED
        )

        out = StringIO()
        call_command('cleanup_raw_content', '--dry-run', stdout=out)

        source.refresh_from_db()
        assert source.raw_content is not None  # Content preserved
        assert source.raw_content_cleared is False

    @pytest.mark.django_db
    def test_cleanup_deletes_content(self):
        """Test cleanup actually deletes content when not dry run."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        source = CrawledSource.objects.create(
            url="https://example.com/cleanup-test",
            title="Cleanup Test",
            source_type="review_article",
            raw_content="<html>content</html>",
            raw_content_cleared=False,
            cleanup_eligible=True,
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.SAVED
        )

        out = StringIO()
        call_command('cleanup_raw_content', stdout=out)

        source.refresh_from_db()
        assert source.raw_content is None
        assert source.raw_content_cleared is True

    @pytest.mark.django_db
    def test_skips_non_eligible_sources(self):
        """Test cleanup skips sources that aren't eligible."""
        from crawler.models import CrawledSource

        # Create non-eligible source (not cleanup_eligible)
        source = CrawledSource.objects.create(
            url="https://example.com/not-eligible",
            title="Not Eligible",
            source_type="review_article",
            raw_content="<html>content</html>",
            raw_content_cleared=False,
            cleanup_eligible=False
        )

        out = StringIO()
        call_command('cleanup_raw_content', stdout=out)

        source.refresh_from_db()
        assert source.raw_content is not None

    @pytest.mark.django_db
    def test_respects_batch_size(self):
        """Test cleanup respects batch size parameter."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        # Create multiple eligible sources
        for i in range(5):
            CrawledSource.objects.create(
                url=f"https://example.com/batch-{i}",
                title=f"Batch {i}",
                source_type="review_article",
                raw_content="<html>content</html>",
                raw_content_cleared=False,
                cleanup_eligible=True,
                extraction_status="processed",
                wayback_status=WaybackStatusChoices.SAVED
            )

        out = StringIO()
        call_command('cleanup_raw_content', '--batch-size=2', stdout=out)

        # Only 2 should be cleaned in this batch
        cleared = CrawledSource.objects.filter(raw_content_cleared=True).count()
        assert cleared == 2

    @pytest.mark.django_db
    def test_reports_cleanup_count(self):
        """Test command reports number cleaned up."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        for i in range(3):
            CrawledSource.objects.create(
                url=f"https://example.com/report-{i}",
                title=f"Report {i}",
                source_type="review_article",
                raw_content="<html>content</html>",
                raw_content_cleared=False,
                cleanup_eligible=True,
                extraction_status="processed",
                wayback_status=WaybackStatusChoices.SAVED
            )

        out = StringIO()
        call_command('cleanup_raw_content', stdout=out)
        output = out.getvalue()

        assert '3' in output  # Should mention the count


class TestCleanupEligibilityQuery:
    """Tests for cleanup eligibility query logic."""

    @pytest.mark.django_db
    def test_query_filters_by_cleanup_eligible(self):
        """Test query filters by cleanup_eligible flag."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        # Create eligible
        CrawledSource.objects.create(
            url="https://example.com/eligible",
            title="Eligible",
            source_type="review_article",
            raw_content="<html>content</html>",
            cleanup_eligible=True,
            raw_content_cleared=False,
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.SAVED
        )

        # Create not eligible
        CrawledSource.objects.create(
            url="https://example.com/not-eligible",
            title="Not Eligible",
            source_type="review_article",
            raw_content="<html>content</html>",
            cleanup_eligible=False,
            raw_content_cleared=False
        )

        pending = CrawledSource.objects.filter(
            cleanup_eligible=True,
            raw_content_cleared=False,
            raw_content__isnull=False
        )

        assert pending.count() == 1

    @pytest.mark.django_db
    def test_query_excludes_already_cleared(self):
        """Test query excludes already cleared sources."""
        from crawler.models import CrawledSource, WaybackStatusChoices

        # Create already cleared
        CrawledSource.objects.create(
            url="https://example.com/already-cleared",
            title="Already Cleared",
            source_type="review_article",
            raw_content=None,
            cleanup_eligible=True,
            raw_content_cleared=True,
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.SAVED
        )

        # Create pending cleanup
        CrawledSource.objects.create(
            url="https://example.com/pending",
            title="Pending",
            source_type="review_article",
            raw_content="<html>content</html>",
            cleanup_eligible=True,
            raw_content_cleared=False,
            extraction_status="processed",
            wayback_status=WaybackStatusChoices.SAVED
        )

        pending = CrawledSource.objects.filter(
            cleanup_eligible=True,
            raw_content_cleared=False,
            raw_content__isnull=False
        )

        assert pending.count() == 1
        assert pending.first().url == "https://example.com/pending"
