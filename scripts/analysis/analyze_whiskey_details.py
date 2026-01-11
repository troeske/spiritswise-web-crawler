#!/usr/bin/env python
"""Analyze WhiskeyDetails and core identity fields population."""
import os
import sys
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from crawler.models import DiscoveredProduct, WhiskeyDetails, DiscoveredBrand

print("=" * 80)
print("WHISKEY DETAILS & CORE IDENTITY FIELDS ANALYSIS")
print(f"Timestamp: {datetime.now().isoformat()}")
print("=" * 80)

# 1. Analyze DiscoveredProduct core identity fields
print("\n[1] DISCOVERED PRODUCT - CORE IDENTITY FIELDS")
print("-" * 60)

products = DiscoveredProduct.objects.filter(product_type='whiskey')
total = products.count()
print(f"Total whiskey products: {total}")

if total > 0:
    # Core identity fields analysis
    with_brand = products.filter(brand__isnull=False).count()
    with_age = products.exclude(age_statement__isnull=True).exclude(age_statement='').count()
    with_region = products.exclude(region__isnull=True).exclude(region='').count()
    with_country = products.exclude(country__isnull=True).exclude(country='').count()
    with_category = products.exclude(category__isnull=True).exclude(category='').count()
    with_abv = products.filter(abv__isnull=False).count()
    with_volume = products.filter(volume_ml__isnull=False).count()

    print(f"\nCore Identity Fields Population:")
    print(f"  Brand (FK):      {with_brand}/{total} ({100*with_brand//total}%)")
    print(f"  Age Statement:   {with_age}/{total} ({100*with_age//total}%)")
    print(f"  Region:          {with_region}/{total} ({100*with_region//total}%)")
    print(f"  Country:         {with_country}/{total} ({100*with_country//total}%)")
    print(f"  Category:        {with_category}/{total} ({100*with_category//total}%)")
    print(f"  ABV:             {with_abv}/{total} ({100*with_abv//total}%)")
    print(f"  Volume (ml):     {with_volume}/{total} ({100*with_volume//total}%)")

    # Sample products with their core fields
    print(f"\nSample Products (first 5):")
    for p in products[:5]:
        brand_name = p.brand.name if p.brand else "MISSING"
        print(f"\n  {p.name[:50]}...")
        print(f"    Brand: {brand_name}")
        print(f"    Age: {p.age_statement or 'MISSING'}")
        print(f"    Region: {p.region or 'MISSING'}")
        print(f"    Country: {p.country or 'MISSING'}")
        print(f"    Category: {p.category or 'MISSING'}")
        print(f"    ABV: {p.abv or 'MISSING'}")

# 2. Analyze WhiskeyDetails
print("\n\n[2] WHISKEY DETAILS MODEL")
print("-" * 60)

whiskey_details = WhiskeyDetails.objects.all()
wd_total = whiskey_details.count()
print(f"Total WhiskeyDetails records: {wd_total}")

if wd_total > 0:
    with_distillery = whiskey_details.exclude(distillery__isnull=True).exclude(distillery='').count()
    with_whiskey_type = whiskey_details.exclude(whiskey_type__isnull=True).exclude(whiskey_type='').count()
    with_mash_bill = whiskey_details.exclude(mash_bill__isnull=True).exclude(mash_bill='').count()
    with_cask_strength = whiskey_details.filter(cask_strength=True).count()
    with_single_cask = whiskey_details.filter(single_cask=True).count()
    with_peated = whiskey_details.filter(peated=True).count()
    with_vintage = whiskey_details.filter(vintage_year__isnull=False).count()
    with_bottling = whiskey_details.filter(bottling_year__isnull=False).count()

    print(f"\nWhiskeyDetails Fields Population:")
    print(f"  Distillery:      {with_distillery}/{wd_total} ({100*with_distillery//wd_total if wd_total else 0}%)")
    print(f"  Whiskey Type:    {with_whiskey_type}/{wd_total} ({100*with_whiskey_type//wd_total if wd_total else 0}%)")
    print(f"  Mash Bill:       {with_mash_bill}/{wd_total} ({100*with_mash_bill//wd_total if wd_total else 0}%)")
    print(f"  Cask Strength:   {with_cask_strength}/{wd_total}")
    print(f"  Single Cask:     {with_single_cask}/{wd_total}")
    print(f"  Peated:          {with_peated}/{wd_total}")
    print(f"  Vintage Year:    {with_vintage}/{wd_total}")
    print(f"  Bottling Year:   {with_bottling}/{wd_total}")

    # Sample WhiskeyDetails
    print(f"\nSample WhiskeyDetails (first 5):")
    for wd in whiskey_details[:5]:
        product_name = wd.product.name[:40] if wd.product else "NO PRODUCT"
        print(f"\n  Product: {product_name}...")
        print(f"    Distillery: {wd.distillery or 'MISSING'}")
        print(f"    Whiskey Type: {wd.whiskey_type or 'MISSING'}")
        print(f"    Mash Bill: {wd.mash_bill or 'MISSING'}")
        print(f"    Peated: {wd.peated}")
        print(f"    Peat Level: {wd.peat_level or 'N/A'}")
else:
    print("  NO WhiskeyDetails records found!")

# 3. Check if products have associated WhiskeyDetails
print("\n\n[3] PRODUCT <-> WHISKEY DETAILS RELATIONSHIP")
print("-" * 60)

products_with_details = 0
for p in products:
    try:
        if hasattr(p, 'whiskey_details') and p.whiskey_details:
            products_with_details += 1
    except:
        pass

print(f"Products with WhiskeyDetails: {products_with_details}/{total}")

# 4. Check brand population
print("\n\n[4] BRAND POPULATION")
print("-" * 60)

brands = DiscoveredBrand.objects.all()
print(f"Total brands in database: {brands.count()}")

if brands.count() > 0:
    print(f"\nSample brands:")
    for b in brands[:10]:
        products_count = DiscoveredProduct.objects.filter(brand=b).count()
        print(f"  {b.name}: {products_count} products")

# 5. Summary
print("\n\n" + "=" * 80)
print("SUMMARY: MANDATORY FIELDS STATUS")
print("=" * 80)

print("""
PROPOSED MANDATORY FIELDS (Easy to find):
  1. Brand         - Usually in product name or clearly stated
  2. Age Statement - On label, "NAS" if not stated
  3. Region        - Usually known for whiskey (Scotland, Kentucky, etc.)
  4. Category      - Whiskey type (Single Malt, Bourbon, etc.)

CURRENT POPULATION:
""")

if total > 0:
    print(f"  Brand:         {100*with_brand//total}% populated")
    print(f"  Age Statement: {100*with_age//total}% populated")
    print(f"  Region:        {100*with_region//total}% populated")
    print(f"  Category:      {100*with_category//total}% populated")

print("""
ISSUES TO FIX:
  1. Brand extraction - parse from product name if not explicit
  2. Age Statement - default to "NAS" if not found
  3. Region - infer from country/distillery if not explicit
  4. Category - infer from product type and name patterns
  5. WhiskeyDetails.distillery - extract from product name
""")
