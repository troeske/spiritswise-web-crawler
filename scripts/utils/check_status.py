#!/usr/bin/env python
"""Check data status."""
import os
import sys
import logging

logging.disable(logging.CRITICAL)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from crawler.models import CrawledSource, DiscoveredProduct

print("=" * 60)
print("DATA STATUS")
print("=" * 60)

# Cached content
sources = CrawledSource.objects.exclude(raw_content='').exclude(raw_content__isnull=True)
print(f"\nCached sources with content: {sources.count()}")
for s in sources[:10]:
    print(f"  - {s.url[:70]}...")

# Products by status
print(f"\nProducts:")
print(f"  - Skeleton: {DiscoveredProduct.objects.filter(status='skeleton').count()}")
print(f"  - Incomplete: {DiscoveredProduct.objects.filter(status='incomplete').count()}")
print(f"  - Complete: {DiscoveredProduct.objects.filter(status='complete').count()}")

# Field population for ALL products
print(f"\nField population (all products):")
total = DiscoveredProduct.objects.count()
if total > 0:
    # Text fields
    text_fields = ['description', 'nose_description', 'palate_description', 'finish_description', 'region', 'category']
    for field in text_fields:
        count = DiscoveredProduct.objects.exclude(**{field: None}).exclude(**{field: ''}).count()
        pct = count / total * 100
        print(f"  - {field}: {count}/{total} ({pct:.0f}%)")

    # Numeric fields (only check for None, not empty string)
    count = DiscoveredProduct.objects.exclude(abv=None).count()
    pct = count / total * 100
    print(f"  - abv: {count}/{total} ({pct:.0f}%)")

    # Brand (special case - FK)
    brand_count = DiscoveredProduct.objects.exclude(brand=None).count()
    pct = brand_count / total * 100
    print(f"  - brand: {brand_count}/{total} ({pct:.0f}%)")
