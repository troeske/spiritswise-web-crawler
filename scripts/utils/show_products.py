#!/usr/bin/env python
"""Show product details."""
import os
import sys
import logging
logging.disable(logging.CRITICAL)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from crawler.models import DiscoveredProduct

print("=" * 70)
print("PRODUCT DETAILS")
print("=" * 70)

for p in DiscoveredProduct.objects.all().order_by('-completeness_score'):
    print(f"\n{p.name[:60]}")
    print(f"  Status: {p.status}, Score: {p.completeness_score}")
    print(f"  ABV: {p.abv}, Region: {p.region}")
    nose = "YES" if p.nose_description else "NO"
    palate = "YES" if p.palate_description else "NO"
    finish = "YES" if p.finish_description else "NO"
    print(f"  Nose: {nose}, Palate: {palate}, Finish: {finish}")
