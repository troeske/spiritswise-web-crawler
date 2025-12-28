"""
Management command to import crawler sources from JSON file.

Usage:
    python manage.py import_sources /path/to/extracted_sources.json
"""

import json
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from crawler.models import CrawlerSource, SourceCategory


# Domain classification rules
RETAILER_DOMAINS = {
    'masterofmalt', 'thewhiskyexchange', 'maltwhisky', 'ewhisky', 'whiskyhaus',
    'whic.de', 'scoma.de', 'bottlebarn', 'mikes-whiskeyhandel', 'sieberts-whiskywelt',
    'abonauten', 'tastillery', 'niococktails', 'd-s-m.com', 'spiritly',
    'topwhiskies', 'whisky-schnack', '089tastings', 'aromaster',
}

REVIEW_DOMAINS = {
    'whiskyadvocate', 'thewhiskeywash', 'breakingbourbon', 'bourbonlens',
    'whiskyexperts', 'vinepair', 'punchdrink', 'decanter', 'tastingtable',
    'chowhound', 'epicurious', 'foodandwine', 'robbreport', 'uproxx',
    'themanual', 'mensjournal', 'gardenandgun', 'gearpatrol', 'forbes',
    'falstaff', 'wineenthusiast', 'wine-searcher', 'diffordsguide',
    'greatdrams', 'liquor.com', 'theeducatedbarfly', 'cluboenologique',
    'thespiritsbusiness', 'thedrinksbusiness', 'fredminnick', 'cocktailbart',
    'bottleraiders', 'hiconsumption', 'manofmany', 'observer', 'gq', 'mashed',
    'thekitchn', 'thespruceeats', 'thetakeout', 'southernliving', 'allrecipes',
    'yahoo', 'aol', 'whiskymag', 'winespectator', 'winemag',
}

COMPETITION_DOMAINS = {
    'sfspiritscomp', 'whiskeycomp', 'iwsc', 'spiritsselection', 'vegasspiritawards',
    'thetastingalliance', 'distilling.com', 'whiskycompetition', 'worldwhiskiesawards',
    'worlddrinksawards', 'internationalspiritschallenge', 'scottishwhiskyawards',
    'oswa.co.uk', 'irishwhiskeyawards', 'globalspiritsmasters', 'nyispiritscompetition',
    'londonspiritscompetition', 'thespiritsbusiness', 'internationalwinechallenge',
    'winesofportugal', 'decanter.com/decanter-awards',
}

PRODUCER_DOMAINS = {
    'heavenhill', 'balconesdistilling', 'milehidistilling', 'xaver-peiting',
}

NEWS_DOMAINS = {
    'tagesschau', 'stern', 't-online', 'focus', 'thueringer-allgemeine',
    'foodanddrink.scotsman', 'irishtimes', 'telegraph', 'derstandard',
    'deutschlandfunk', 'ft.com', 'nationalgeographic', 'therakyatpost',
    'restaurantindia', 'gqindia', 'businessoffashion', 'lonelyplanet',
}

DATABASE_DOMAINS = {
    'whiskybase', 'whiskyflavour',
}


def categorize_source(name, base_url=''):
    """Determine source category based on name and URL."""
    combined = f"{name} {base_url}".lower()

    for pattern in DATABASE_DOMAINS:
        if pattern in combined:
            return SourceCategory.DATABASE

    for pattern in COMPETITION_DOMAINS:
        if pattern in combined:
            return SourceCategory.COMPETITION

    for pattern in PRODUCER_DOMAINS:
        if pattern in combined:
            return SourceCategory.PRODUCER

    for pattern in RETAILER_DOMAINS:
        if pattern in combined:
            return SourceCategory.RETAILER

    for pattern in NEWS_DOMAINS:
        if pattern in combined:
            return SourceCategory.NEWS

    for pattern in REVIEW_DOMAINS:
        if pattern in combined:
            return SourceCategory.REVIEW

    # Default to review for spirits-focused content
    return SourceCategory.REVIEW


def determine_requirements(domain):
    """Determine technical requirements based on domain."""
    domain_lower = domain.lower()

    # Domains known to require JavaScript
    js_required = any(x in domain_lower for x in [
        'forbes', 'robbreport', 'decanter', 'vinepair', 'yahoo', 'aol',
        'nytimes', 'telegraph', 'businessoffashion',
    ])

    # Domains known to need proxy
    proxy_required = any(x in domain_lower for x in [
        'forbes', 'robbreport', 'gq', 'businessoffashion', 'ft.com',
    ])

    return js_required, proxy_required


class Command(BaseCommand):
    help = 'Import crawler sources from JSON file'

    def add_arguments(self, parser):
        parser.add_argument('json_file', type=str, help='Path to JSON file with sources')
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be imported without saving'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            default=True,
            help='Skip sources that already exist (default: True)'
        )

    def handle(self, *args, **options):
        json_file = options['json_file']
        dry_run = options['dry_run']
        skip_existing = options['skip_existing']

        # Load sources from JSON
        with open(json_file, 'r', encoding='utf-8') as f:
            sources = json.load(f)

        self.stdout.write(f"Found {len(sources)} sources in {json_file}")

        created = 0
        skipped = 0
        errors = 0

        for source_data in sources:
            name = source_data['name']
            base_url = source_data['base_url']
            product_type = source_data['product_type']

            # Generate slug
            slug = slugify(name)

            # Check if exists
            if skip_existing and CrawlerSource.objects.filter(slug=slug).exists():
                self.stdout.write(f"  Skipping (exists): {name}")
                skipped += 1
                continue

            # Categorize
            category = categorize_source(name, base_url)
            js_required, proxy_required = determine_requirements(base_url)

            # Prepare data
            source_record = {
                'name': name,
                'slug': slug,
                'base_url': base_url,
                'product_types': [product_type],
                'category': category,
                'is_active': True,
                'priority': 5,
                'crawl_frequency_hours': 168,  # Weekly
                'rate_limit_requests_per_minute': 5,
                'requires_javascript': js_required,
                'requires_proxy': proxy_required,
            }

            if dry_run:
                self.stdout.write(
                    f"  Would create: {name} ({category}) "
                    f"[JS:{js_required}, Proxy:{proxy_required}]"
                )
            else:
                try:
                    CrawlerSource.objects.create(**source_record)
                    self.stdout.write(self.style.SUCCESS(
                        f"  Created: {name} ({category})"
                    ))
                    created += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"  Error creating {name}: {e}"
                    ))
                    errors += 1

        # Summary
        self.stdout.write("")
        self.stdout.write("="*60)
        self.stdout.write(f"Import complete!")
        self.stdout.write(f"  Created: {created}")
        self.stdout.write(f"  Skipped: {skipped}")
        self.stdout.write(f"  Errors: {errors}")
