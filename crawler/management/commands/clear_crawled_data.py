"""
Django management command to clear all crawled data for fresh E2E testing.

This command deletes data in the correct order to respect foreign key constraints.
USE WITH CAUTION - this permanently deletes data!
"""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Clear all crawled data for fresh E2E testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Confirm deletion (required to proceed)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be deleted without actually deleting",
        )
        parser.add_argument(
            "--keep-sources",
            action="store_true",
            help="Keep CrawlerSource and CrawlSchedule configuration (only clear results)",
        )
        parser.add_argument(
            "--keep-brands",
            action="store_true",
            help="Keep DiscoveredBrand data",
        )

    def handle(self, *args, **options):
        from crawler.models import (
            # Phase 1: Cascade-dependent models
            ArticleProductMention,
            ProductAvailability,
            PurchaseRecommendation,
            ProductAward,
            ProductPrice,
            ProductRating,
            ProductImage,
            ProductSource,
            ProductFieldSource,
            BrandAward,
            BrandSource,
            SourceMetrics,
            ProductCandidate,
            PriceHistory,
            PriceAlert,
            NewRelease,
            # Phase 2: Core crawled data
            DiscoveryResult,
            CrawledArticle,
            CrawledSource,
            CrawledURL,
            CrawlCost,
            CrawlError,
            DiscoveryJob,
            CrawlJob,
            # Phase 3: Product and brand data
            DiscoveredProduct,
            DiscoveredBrand,
            # Phase 4: Configuration
            SearchTerm,
            DiscoverySourceConfig,
            CrawlerKeyword,
            CrawlerSource,
            CrawlSchedule,
            # Phase 5: Metrics
            CrawlerMetrics,
            ShopInventory,
        )

        dry_run = options["dry_run"]
        confirm = options["confirm"]
        keep_sources = options["keep_sources"]
        keep_brands = options["keep_brands"]

        if not confirm and not dry_run:
            raise CommandError(
                "This command will DELETE ALL CRAWLED DATA. "
                "Use --confirm to proceed or --dry-run to preview."
            )

        # Define deletion order (respects FK constraints)
        deletion_phases = [
            # Phase 1: Cascade-dependent models (delete first)
            ("Phase 1: Cascade-dependent models", [
                ("ArticleProductMention", ArticleProductMention),
                ("ProductAvailability", ProductAvailability),
                ("PurchaseRecommendation", PurchaseRecommendation),
                ("ProductAward", ProductAward),
                ("ProductPrice", ProductPrice),
                ("ProductRating", ProductRating),
                ("ProductImage", ProductImage),
                ("ProductSource", ProductSource),
                ("ProductFieldSource", ProductFieldSource),
                ("BrandAward", BrandAward),
                ("BrandSource", BrandSource),
                ("SourceMetrics", SourceMetrics),
                ("ProductCandidate", ProductCandidate),
                ("PriceHistory", PriceHistory),
                ("PriceAlert", PriceAlert),
                ("NewRelease", NewRelease),
            ]),
            # Phase 2: Core crawled data
            ("Phase 2: Core crawled data", [
                ("DiscoveryResult", DiscoveryResult),
                ("CrawledArticle", CrawledArticle),
                ("CrawledSource", CrawledSource),
                ("CrawledURL", CrawledURL),
                ("CrawlCost", CrawlCost),
                ("CrawlError", CrawlError),
                ("DiscoveryJob", DiscoveryJob),
                ("CrawlJob", CrawlJob),
            ]),
            # Phase 3: Product and brand data
            ("Phase 3: Product and brand data", [
                ("DiscoveredProduct", DiscoveredProduct),
            ]),
            # Phase 5: Metrics
            ("Phase 5: Metrics and inventory", [
                ("CrawlerMetrics", CrawlerMetrics),
                ("ShopInventory", ShopInventory),
            ]),
        ]

        # Optionally add brand deletion
        if not keep_brands:
            deletion_phases[2][1].append(("DiscoveredBrand", DiscoveredBrand))

        # Optionally add configuration deletion
        if not keep_sources:
            deletion_phases.append(
                ("Phase 4: Configuration (--keep-sources=False)", [
                    ("SearchTerm", SearchTerm),
                    ("DiscoverySourceConfig", DiscoverySourceConfig),
                    ("CrawlerKeyword", CrawlerKeyword),
                    ("CrawlerSource", CrawlerSource),
                    ("CrawlSchedule", CrawlSchedule),
                ])
            )

        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No data will be deleted"))
        else:
            self.stdout.write(self.style.ERROR("DELETING ALL CRAWLED DATA"))
        self.stdout.write("=" * 60 + "\n")

        total_deleted = 0

        try:
            with transaction.atomic():
                for phase_name, models in deletion_phases:
                    self.stdout.write(f"\n{self.style.HTTP_INFO(phase_name)}")
                    self.stdout.write("-" * 40)

                    for model_name, model_class in models:
                        count = model_class.objects.count()
                        if dry_run:
                            self.stdout.write(
                                f"  {model_name}: {count} records (would delete)"
                            )
                        else:
                            deleted, _ = model_class.objects.all().delete()
                            self.stdout.write(
                                f"  {model_name}: {count} records deleted"
                            )
                            total_deleted += deleted

                if dry_run:
                    # Rollback transaction for dry run
                    raise DryRunException()

        except DryRunException:
            pass  # Expected for dry run

        self.stdout.write("\n" + "=" * 60)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"DRY RUN COMPLETE - No changes made")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"DELETION COMPLETE - {total_deleted} total records deleted")
            )
        self.stdout.write("=" * 60 + "\n")

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS("\nDatabase is now ready for fresh E2E testing!")
            )


class DryRunException(Exception):
    """Exception to trigger rollback during dry run."""
    pass
