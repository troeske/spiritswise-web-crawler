"""
Management command to import search terms from JSON file.

Usage:
    python manage.py import_search_terms /path/to/search_terms.json
    python manage.py import_search_terms --preset whiskey
    python manage.py import_search_terms --preset port
    python manage.py import_search_terms --preset all

JSON Format:
{
    "terms": [
        {
            "search_query": "best whiskey 2026",
            "category": "best_lists",
            "product_type": "whiskey",
            "priority": 100,
            "max_results": 10,
            "is_active": true,
            "seasonal_start_month": null,
            "seasonal_end_month": null
        },
        ...
    ]
}
"""

import json
from django.core.management.base import BaseCommand, CommandError
from crawler.models import SearchTerm, SearchTermCategory, SearchTermProductType


# Preset search terms for whiskey
WHISKEY_SEARCH_TERMS = [
    # Best Lists - High Priority
    {"search_query": "best whiskey {year}", "category": "best_lists", "priority": 100},
    {"search_query": "best bourbon {year}", "category": "best_lists", "priority": 100},
    {"search_query": "best scotch {year}", "category": "best_lists", "priority": 100},
    {"search_query": "best rye whiskey {year}", "category": "best_lists", "priority": 100},
    {"search_query": "best irish whiskey {year}", "category": "best_lists", "priority": 95},
    {"search_query": "best japanese whisky {year}", "category": "best_lists", "priority": 95},
    {"search_query": "top rated whiskey {year}", "category": "best_lists", "priority": 90},
    {"search_query": "whiskey of the year {year}", "category": "best_lists", "priority": 100},
    # Awards
    {"search_query": "whiskey awards {year} winners", "category": "awards", "priority": 95},
    {"search_query": "IWSC whiskey {year}", "category": "awards", "priority": 90},
    {"search_query": "San Francisco World Spirits whiskey {year}", "category": "awards", "priority": 90},
    {"search_query": "World Whiskies Awards {year}", "category": "awards", "priority": 90},
    # New Releases
    {"search_query": "new whiskey releases {year}", "category": "new_releases", "priority": 85},
    {"search_query": "new bourbon releases {year}", "category": "new_releases", "priority": 85},
    {"search_query": "limited edition whiskey {year}", "category": "new_releases", "priority": 80},
    {"search_query": "whiskey new arrivals {year}", "category": "new_releases", "priority": 75},
    # Style & Flavor
    {"search_query": "best peated whiskey", "category": "style", "priority": 70},
    {"search_query": "best cask strength bourbon", "category": "style", "priority": 70},
    {"search_query": "best single malt whiskey", "category": "style", "priority": 75},
    {"search_query": "best sherry cask whiskey", "category": "style", "priority": 65},
    {"search_query": "best smoky whiskey", "category": "style", "priority": 65},
    {"search_query": "best sweet bourbon", "category": "style", "priority": 60},
    # Value
    {"search_query": "best whiskey under $50", "category": "value", "priority": 80},
    {"search_query": "best bourbon under $30", "category": "value", "priority": 80},
    {"search_query": "best cheap whiskey {year}", "category": "value", "priority": 75},
    {"search_query": "best value whiskey {year}", "category": "value", "priority": 75},
    {"search_query": "best affordable scotch", "category": "value", "priority": 70},
    # Regional
    {"search_query": "best Kentucky bourbon", "category": "regional", "priority": 65},
    {"search_query": "best Islay whisky", "category": "regional", "priority": 65},
    {"search_query": "best Speyside whisky", "category": "regional", "priority": 60},
    {"search_query": "best Texas whiskey", "category": "regional", "priority": 55},
    {"search_query": "best Tennessee whiskey", "category": "regional", "priority": 55},
    # Seasonal
    {"search_query": "best whiskey gifts {year}", "category": "seasonal", "priority": 85, "seasonal_start_month": 11, "seasonal_end_month": 12},
    {"search_query": "holiday whiskey {year}", "category": "seasonal", "priority": 80, "seasonal_start_month": 11, "seasonal_end_month": 12},
    {"search_query": "whiskey gift guide {year}", "category": "seasonal", "priority": 80, "seasonal_start_month": 10, "seasonal_end_month": 12},
    {"search_query": "Father's Day whiskey {year}", "category": "seasonal", "priority": 75, "seasonal_start_month": 5, "seasonal_end_month": 6},
]

# Preset search terms for port wine
PORT_SEARCH_TERMS = [
    # Best Lists - High Priority
    {"search_query": "best port wine {year}", "category": "best_lists", "priority": 100},
    {"search_query": "best vintage port {year}", "category": "best_lists", "priority": 100},
    {"search_query": "best tawny port {year}", "category": "best_lists", "priority": 95},
    {"search_query": "best ruby port {year}", "category": "best_lists", "priority": 95},
    {"search_query": "best LBV port {year}", "category": "best_lists", "priority": 90},
    {"search_query": "top rated port wine {year}", "category": "best_lists", "priority": 90},
    # Awards
    {"search_query": "port wine awards {year} winners", "category": "awards", "priority": 95},
    {"search_query": "IWSC port wine {year}", "category": "awards", "priority": 90},
    {"search_query": "Decanter port wine awards {year}", "category": "awards", "priority": 90},
    {"search_query": "Wines of Portugal awards port {year}", "category": "awards", "priority": 85},
    # New Releases
    {"search_query": "new vintage port releases {year}", "category": "new_releases", "priority": 85},
    {"search_query": "declared vintage port {year}", "category": "new_releases", "priority": 90},
    {"search_query": "port wine new arrivals {year}", "category": "new_releases", "priority": 75},
    # Style
    {"search_query": "best aged tawny port 20 year", "category": "style", "priority": 70},
    {"search_query": "best colheita port", "category": "style", "priority": 70},
    {"search_query": "best single quinta port", "category": "style", "priority": 65},
    {"search_query": "best white port", "category": "style", "priority": 60},
    {"search_query": "best rose port", "category": "style", "priority": 55},
    # Value
    {"search_query": "best port wine under $50", "category": "value", "priority": 80},
    {"search_query": "best affordable port wine", "category": "value", "priority": 75},
    {"search_query": "best value tawny port", "category": "value", "priority": 70},
    {"search_query": "best cheap port wine", "category": "value", "priority": 65},
    # Producers
    {"search_query": "best Taylor's port wines", "category": "regional", "priority": 60},
    {"search_query": "best Graham's port wines", "category": "regional", "priority": 60},
    {"search_query": "best Fonseca port wines", "category": "regional", "priority": 55},
    {"search_query": "best Dow's port wines", "category": "regional", "priority": 55},
    {"search_query": "best Niepoort port wines", "category": "regional", "priority": 50},
    # Seasonal
    {"search_query": "port wine gifts {year}", "category": "seasonal", "priority": 85, "seasonal_start_month": 11, "seasonal_end_month": 12},
    {"search_query": "holiday port wine {year}", "category": "seasonal", "priority": 80, "seasonal_start_month": 11, "seasonal_end_month": 12},
    {"search_query": "port wine for christmas", "category": "seasonal", "priority": 80, "seasonal_start_month": 11, "seasonal_end_month": 12},
]


class Command(BaseCommand):
    """Import search terms from JSON file or preset."""

    help = "Import search terms from JSON file or use preset terms"

    def add_arguments(self, parser):
        parser.add_argument(
            "json_file",
            nargs="?",
            type=str,
            help="Path to JSON file with search terms",
        )
        parser.add_argument(
            "--preset",
            type=str,
            choices=["whiskey", "port", "all"],
            help="Use preset search terms instead of JSON file",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing search terms before import",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be imported without making changes",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing terms instead of skipping duplicates",
        )

    def handle(self, *args, **options):
        json_file = options.get("json_file")
        preset = options.get("preset")
        clear = options.get("clear", False)
        dry_run = options.get("dry_run", False)
        update = options.get("update", False)

        if not json_file and not preset:
            raise CommandError("Must specify either a JSON file or --preset option")

        # Clear if requested
        if clear and not dry_run:
            count = SearchTerm.objects.count()
            SearchTerm.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"Cleared {count} existing search terms"))

        # Load terms
        if preset:
            terms = self._load_preset(preset)
        else:
            terms = self._load_json(json_file)

        if not terms:
            raise CommandError("No terms to import")

        self.stdout.write(f"\nImporting {len(terms)} search term(s)...")

        # Import terms
        created = 0
        updated = 0
        skipped = 0

        for term_data in terms:
            result = self._import_term(term_data, dry_run, update)
            if result == "created":
                created += 1
            elif result == "updated":
                updated += 1
            else:
                skipped += 1

        # Summary
        self.stdout.write("")
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes made"))

        self.stdout.write(self.style.SUCCESS(f"Created: {created}"))
        if update:
            self.stdout.write(self.style.SUCCESS(f"Updated: {updated}"))
        self.stdout.write(self.style.NOTICE(f"Skipped: {skipped}"))
        self.stdout.write("")

    def _load_preset(self, preset):
        """Load preset search terms."""
        terms = []

        if preset in ("whiskey", "all"):
            for term in WHISKEY_SEARCH_TERMS:
                term_copy = term.copy()
                term_copy["product_type"] = "whiskey"
                terms.append(term_copy)
            self.stdout.write(f"Loaded {len(WHISKEY_SEARCH_TERMS)} whiskey search terms")

        if preset in ("port", "all"):
            for term in PORT_SEARCH_TERMS:
                term_copy = term.copy()
                term_copy["product_type"] = "port_wine"
                terms.append(term_copy)
            self.stdout.write(f"Loaded {len(PORT_SEARCH_TERMS)} port wine search terms")

        return terms

    def _load_json(self, json_file):
        """Load search terms from JSON file."""
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            raise CommandError(f"File not found: {json_file}")
        except json.JSONDecodeError as e:
            raise CommandError(f"Invalid JSON: {e}")

        if "terms" in data:
            terms = data["terms"]
        elif isinstance(data, list):
            terms = data
        else:
            raise CommandError("JSON must contain 'terms' array or be an array itself")

        self.stdout.write(f"Loaded {len(terms)} search terms from {json_file}")
        return terms

    def _import_term(self, term_data, dry_run, update):
        """Import a single search term."""
        search_query = term_data.get("search_query")
        if not search_query:
            self.stdout.write(self.style.ERROR(f"  Skipping term without template"))
            return "skipped"

        # Validate category
        category = term_data.get("category", "best_lists")
        if category not in SearchTermCategory.values:
            self.stdout.write(self.style.ERROR(f"  Invalid category '{category}' for: {search_query}"))
            return "skipped"

        # Validate product type
        product_type = term_data.get("product_type", "whiskey")
        if product_type not in SearchTermProductType.values:
            self.stdout.write(self.style.ERROR(f"  Invalid product_type '{product_type}' for: {search_query}"))
            return "skipped"

        # Check for existing
        existing = SearchTerm.objects.filter(
            search_query=search_query,
            product_type=product_type,
        ).first()

        if existing:
            if update and not dry_run:
                existing.category = category
                existing.priority = term_data.get("priority", 100)
                existing.is_active = term_data.get("is_active", True)
                existing.seasonal_start_month = term_data.get("seasonal_start_month")
                existing.seasonal_end_month = term_data.get("seasonal_end_month")
                existing.save()
                self.stdout.write(f"  Updated: {search_query}")
                return "updated"
            else:
                self.stdout.write(f"  Skipped (exists): {search_query}")
                return "skipped"

        # Create new term
        if dry_run:
            self.stdout.write(f"  Would create: {search_query} ({category}/{product_type})")
            return "created"

        SearchTerm.objects.create(
            search_query=search_query,
            category=category,
            product_type=product_type,
            priority=term_data.get("priority", 100),
            is_active=term_data.get("is_active", True),
            seasonal_start_month=term_data.get("seasonal_start_month"),
            seasonal_end_month=term_data.get("seasonal_end_month"),
        )
        self.stdout.write(f"  Created: {search_query}")
        return "created"
