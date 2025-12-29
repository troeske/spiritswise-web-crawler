"""
Management command to test the SerpAPI discovery pipeline with real queries.

This is a live test command that uses actual SerpAPI quota.

Usage:
    # Dry run - show what would be searched (no API calls)
    python manage.py test_serpapi_discovery --dry-run

    # Discovery only (5 queries)
    python manage.py test_serpapi_discovery --discovery-only

    # Discovery + price enrichment (5 + N queries)
    python manage.py test_serpapi_discovery --enrich-prices --limit 10

    # Full enrichment for top products (5 + 4*N queries)
    python manage.py test_serpapi_discovery --full-enrich --limit 5

Query Budget (with ~220 free queries):
    - Discovery only: 5 queries
    - Discovery + 20 price lookups: 25 queries
    - Discovery + 10 full enrichments: 45 queries
"""

import logging
from datetime import datetime

from django.core.management.base import BaseCommand
from django.db import transaction

from crawler.models import DiscoveredProduct, DiscoveredProductStatus
from crawler.discovery.serpapi.client import SerpAPIClient
from crawler.discovery.serpapi.queries import QueryBuilder
from crawler.discovery.serpapi.rate_limiter import RateLimiter, QuotaTracker
from crawler.discovery.search.target_extractor import TargetURLExtractor
from crawler.discovery.search.config import SearchConfig
from crawler.discovery.enrichment.orchestrator import ProductEnricher
from crawler.discovery.enrichment.price_finder import PriceFinder

logger = logging.getLogger(__name__)


# Focused test queries for 2025 whiskey awards
TEST_QUERIES = [
    "best bourbon whiskey 2025 awards",
    "best rye whiskey 2025 awards",
    "bourbon of the year 2025",
    "whisky advocate 2025 top rated bourbon",
    "san francisco world spirits competition 2025 bourbon gold medal",
]


class Command(BaseCommand):
    help = "Test SerpAPI discovery pipeline with real queries"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be done without making API calls",
        )
        parser.add_argument(
            "--discovery-only",
            action="store_true",
            help="Only run discovery searches, don't enrich",
        )
        parser.add_argument(
            "--enrich-prices",
            action="store_true",
            help="Enrich discovered products with price data only",
        )
        parser.add_argument(
            "--full-enrich",
            action="store_true",
            help="Full enrichment (prices, reviews, images, articles)",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Maximum products to enrich (default: 10)",
        )
        parser.add_argument(
            "--queries",
            type=int,
            default=5,
            help="Number of discovery queries to run (default: 5)",
        )
        parser.add_argument(
            "--show-quota",
            action="store_true",
            help="Show current SerpAPI quota status",
        )

    def handle(self, *args, **options):
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("SerpAPI Discovery Pipeline - Live Test")
        self.stdout.write("=" * 60 + "\n")

        # Initialize components
        try:
            self.client = SerpAPIClient()
            self.rate_limiter = RateLimiter()
            self.quota_tracker = QuotaTracker(rate_limiter=self.rate_limiter)
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to initialize: {e}"))
            return

        # Show quota status
        if options["show_quota"] or options["dry_run"]:
            self._show_quota()

        if options["show_quota"] and not any([
            options["discovery_only"],
            options["enrich_prices"],
            options["full_enrich"],
        ]):
            return

        # Calculate expected query usage
        num_queries = min(options["queries"], len(TEST_QUERIES))
        enrich_limit = options["limit"]

        expected_usage = num_queries
        if options["enrich_prices"]:
            expected_usage += enrich_limit  # 1 query per product
        elif options["full_enrich"]:
            expected_usage += enrich_limit * 4  # 4 queries per product

        self.stdout.write(f"Expected query usage: {expected_usage}")
        self.stdout.write(f"  - Discovery: {num_queries} queries")
        if options["enrich_prices"]:
            self.stdout.write(f"  - Price enrichment: up to {enrich_limit} queries")
        elif options["full_enrich"]:
            self.stdout.write(f"  - Full enrichment: up to {enrich_limit * 4} queries")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("\nDRY RUN - No API calls will be made"))
            self._show_test_plan(num_queries)
            return

        # Confirm before proceeding
        self.stdout.write(f"\nThis will use approximately {expected_usage} SerpAPI queries.")

        # Run discovery
        discovered_products = self._run_discovery(num_queries)

        if not discovered_products:
            self.stdout.write(self.style.WARNING("No products discovered"))
            return

        # Run enrichment if requested
        if options["enrich_prices"]:
            self._run_price_enrichment(discovered_products[:enrich_limit])
        elif options["full_enrich"]:
            self._run_full_enrichment(discovered_products[:enrich_limit])

        # Final summary
        self._show_summary()

    def _show_quota(self):
        """Display current SerpAPI quota status."""
        try:
            stats = self.quota_tracker.get_usage_stats()
            self.stdout.write("\nSerpAPI Quota Status:")
            self.stdout.write(f"  Hourly remaining: {stats.get('hourly_remaining', 'N/A')}/{stats.get('hourly_limit', 'N/A')}")
            self.stdout.write(f"  Monthly remaining: {stats.get('monthly_remaining', 'N/A')}/{stats.get('monthly_limit', 'N/A')}")
            self.stdout.write("")
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"Could not fetch quota: {e}"))

    def _show_test_plan(self, num_queries: int):
        """Show what would be tested in dry-run mode."""
        self.stdout.write("\nTest queries that would be executed:")
        for i, query in enumerate(TEST_QUERIES[:num_queries], 1):
            self.stdout.write(f"  {i}. {query}")

        self.stdout.write("\nPipeline steps:")
        self.stdout.write("  1. Execute discovery queries via SerpAPI")
        self.stdout.write("  2. Parse organic results from each search")
        self.stdout.write("  3. Extract and prioritize target URLs")
        self.stdout.write("  4. Filter out excluded domains (social media, etc.)")
        self.stdout.write("  5. Create DiscoveredProduct entries for unique URLs")
        self.stdout.write("  6. (Optional) Enrich products with price/review data")

    def _run_discovery(self, num_queries: int) -> list:
        """Run discovery queries and extract products."""
        self.stdout.write("\n--- Phase 1: Discovery ---\n")

        config = SearchConfig()
        extractor = TargetURLExtractor(config=config)

        all_targets = []
        queries_used = 0

        for query in TEST_QUERIES[:num_queries]:
            self.stdout.write(f"Searching: {query}")

            try:
                # Check rate limit
                if not self.rate_limiter.can_make_request():
                    self.stdout.write(self.style.WARNING("Rate limit reached, stopping"))
                    break

                # Execute search
                response = self.client.google_search(query=query)
                self.rate_limiter.record_request()
                queries_used += 1

                # Parse results
                organic_results = response.get("organic_results", [])
                self.stdout.write(f"  Found {len(organic_results)} organic results")

                # Extract targets
                targets = extractor.extract_targets(response)
                self.stdout.write(f"  Extracted {len(targets)} valid targets")

                all_targets.extend(targets)

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error: {e}"))

        self.stdout.write(f"\nDiscovery complete: {queries_used} queries used")
        self.stdout.write(f"Total targets extracted: {len(all_targets)}")

        # Deduplicate by URL
        seen_urls = set()
        unique_targets = []
        for target in all_targets:
            url = target.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_targets.append(target)

        self.stdout.write(f"Unique targets after deduplication: {len(unique_targets)}")

        # Create DiscoveredProduct entries
        products = self._create_products_from_targets(unique_targets)
        return products

    def _create_products_from_targets(self, targets: list) -> list:
        """Create DiscoveredProduct entries from extracted targets."""
        self.stdout.write("\n--- Creating Product Entries ---\n")

        products = []
        created_count = 0
        updated_count = 0

        for target in targets:
            url = target.get("url", "")
            title = target.get("title", "")
            source = target.get("source", "")

            if not url:
                continue

            # Try to find existing product by URL
            existing = DiscoveredProduct.objects.filter(
                source_url=url
            ).first()

            if existing:
                updated_count += 1
                products.append(existing)
                continue

            # Create new product
            try:
                with transaction.atomic():
                    product = DiscoveredProduct.objects.create(
                        source_url=url,
                        product_type="whisky",
                        status=DiscoveredProductStatus.SKELETON,
                        enrichment_status="pending",
                        extracted_data={
                            "name": title,
                            "source": source,
                            "discovery_method": "serpapi_search",
                            "discovery_query": "2025 bourbon/rye awards",
                            "priority": target.get("priority", 0),
                        },
                    )
                    products.append(product)
                    created_count += 1

            except Exception as e:
                self.stdout.write(self.style.WARNING(f"  Could not create: {e}"))

        self.stdout.write(f"Products created: {created_count}")
        self.stdout.write(f"Products existing: {updated_count}")

        return products

    def _run_price_enrichment(self, products: list):
        """Enrich products with price data only."""
        self.stdout.write("\n--- Phase 2: Price Enrichment ---\n")

        price_finder = PriceFinder(client=self.client)
        enriched_count = 0

        for product in products:
            name = product.extracted_data.get("name", "Unknown")
            self.stdout.write(f"Finding prices for: {name[:50]}...")

            try:
                if not self.rate_limiter.can_make_request():
                    self.stdout.write(self.style.WARNING("Rate limit reached"))
                    break

                prices = price_finder.find_prices(product)
                self.rate_limiter.record_request()

                if prices:
                    self.stdout.write(f"  Found {len(prices)} prices")
                    # Update product
                    product.price_history = prices
                    if prices:
                        best = min(prices, key=lambda p: p.get("price", float("inf")))
                        product.best_price = best
                    product.enrichment_status = "partial"
                    product.save()
                    enriched_count += 1
                else:
                    self.stdout.write("  No prices found")

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error: {e}"))

        self.stdout.write(f"\nPrice enrichment complete: {enriched_count} products updated")

    def _run_full_enrichment(self, products: list):
        """Full enrichment with all finders."""
        self.stdout.write("\n--- Phase 2: Full Enrichment ---\n")

        enricher = ProductEnricher(client=self.client)
        results = []

        for product in products:
            name = product.extracted_data.get("name", "Unknown")
            self.stdout.write(f"Enriching: {name[:50]}...")

            try:
                if not self.rate_limiter.can_make_request():
                    self.stdout.write(self.style.WARNING("Rate limit reached"))
                    break

                result = enricher.enrich_product(product)
                # Record 4 API calls (shopping, search, images, news)
                for _ in range(4):
                    self.rate_limiter.record_request()

                results.append(result)

                self.stdout.write(
                    f"  Prices: {result['prices_found']}, "
                    f"Reviews: {result['reviews_found']}, "
                    f"Images: {result['images_found']}, "
                    f"Articles: {result['articles_found']}"
                )

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  Error: {e}"))

        success_count = sum(1 for r in results if r.get("success"))
        self.stdout.write(f"\nFull enrichment complete: {success_count}/{len(results)} successful")

    def _show_summary(self):
        """Show final summary of test results."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("Test Summary")
        self.stdout.write("=" * 60 + "\n")

        # Count products by status
        total = DiscoveredProduct.objects.count()
        skeleton = DiscoveredProduct.objects.filter(
            status=DiscoveredProductStatus.SKELETON
        ).count()
        pending = DiscoveredProduct.objects.filter(
            enrichment_status="pending"
        ).count()
        enriched = DiscoveredProduct.objects.filter(
            enrichment_status__in=["partial", "completed"]
        ).count()

        self.stdout.write(f"Total products in database: {total}")
        self.stdout.write(f"  - Skeleton status: {skeleton}")
        self.stdout.write(f"  - Pending enrichment: {pending}")
        self.stdout.write(f"  - Enriched: {enriched}")

        # Show recent products
        recent = DiscoveredProduct.objects.order_by("-created_at")[:5]
        if recent:
            self.stdout.write("\nRecent products:")
            for p in recent:
                name = p.extracted_data.get("name", "Unknown")[:40]
                self.stdout.write(f"  - {name} ({p.enrichment_status})")

        self.stdout.write(self.style.SUCCESS("\nTest completed successfully!"))
        self.stdout.write("Check PostgreSQL database for full results.\n")
