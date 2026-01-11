#!/usr/bin/env python
"""
Task 5: Enable enrichment for existing skeleton products (quiet version).

This script:
1. Enables enrichment on all competition CrawlSchedules
2. Triggers the enrich_skeletons task for existing products
"""
import os
import sys
import logging

# Suppress all debug logging - especially Django DB which prints raw SQL with content
logging.getLogger('django.db.backends').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# Set root logger to INFO
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s'
)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from crawler.models import CrawlSchedule, DiscoveredProduct

print("=" * 60)
print("ENRICHMENT FOR SKELETON PRODUCTS")
print("=" * 60)

# Step 1: Check current skeleton count
skeleton_count = DiscoveredProduct.objects.filter(status='skeleton').count()
incomplete_count = DiscoveredProduct.objects.filter(status='incomplete').count()
print(f"\nCurrent products:")
print(f"  - Skeleton: {skeleton_count}")
print(f"  - Incomplete: {incomplete_count}")

# Step 2: Enable enrichment on competition schedules
print("\nEnabling enrichment on CrawlSchedules...")
schedules = CrawlSchedule.objects.all()
for s in schedules:
    old_value = s.enrich
    s.enrich = True
    s.save()
    print(f"  - {s.name}: enrich={old_value} -> True")

# Step 3: Try to run enrichment directly (if Celery not available)
print("\nAttempting to run enrichment...")

try:
    from crawler.services.discovery_orchestrator import DiscoveryOrchestrator

    orchestrator = DiscoveryOrchestrator()

    # Get ALL skeleton products to enrich
    skeletons = DiscoveredProduct.objects.filter(status='skeleton')

    print(f"\nEnriching {skeletons.count()} skeleton products...")

    for product in skeletons:
        print(f"\n  Processing: {product.name[:60]}...")
        try:
            # Try to enrich using SerpAPI search
            result = orchestrator._search_and_extract_product(
                product_name=product.name,
                brand=product.brand.name if product.brand else None,
                product_type=product.product_type or 'whiskey',
            )

            if result and result.get('success') and result.get('data'):
                data = result['data']
                print(f"    Found enrichment data!")
                print(f"    Keys: {list(data.keys())[:8]}...")

                # Update product with enriched data
                enriched_count = 0
                if data.get('abv'):
                    product.abv = data['abv']
                    print(f"    - ABV: {data['abv']}")
                    enriched_count += 1
                if data.get('description'):
                    product.description = data['description'][:500] if len(data.get('description', '')) > 500 else data.get('description')
                    print(f"    - Description: YES ({len(data['description'])} chars)")
                    enriched_count += 1
                if data.get('nose_description'):
                    product.nose_description = data['nose_description']
                    print(f"    - Nose: YES")
                    enriched_count += 1
                if data.get('palate_description'):
                    product.palate_description = data['palate_description']
                    print(f"    - Palate: YES")
                    enriched_count += 1
                if data.get('finish_description'):
                    product.finish_description = data['finish_description']
                    print(f"    - Finish: YES")
                    enriched_count += 1
                if data.get('region'):
                    product.region = data['region']
                    print(f"    - Region: {data['region']}")
                    enriched_count += 1
                if data.get('category'):
                    product.category = data['category']
                    print(f"    - Category: {data['category']}")
                    enriched_count += 1
                if data.get('brand'):
                    from crawler.services.product_saver import get_or_create_brand
                    brand_obj, _ = get_or_create_brand(data)
                    if brand_obj:
                        product.brand = brand_obj
                        print(f"    - Brand: {brand_obj.name}")
                        enriched_count += 1

                if enriched_count > 0:
                    product.status = 'incomplete'  # Upgrade from skeleton
                    product.save()
                    print(f"    Status: skeleton -> incomplete ({enriched_count} fields enriched)")
                else:
                    print(f"    No usable enrichment data in response")

            elif result and not result.get('success'):
                print(f"    Enrichment failed: {result.get('reason', 'unknown')}")
            else:
                print(f"    No enrichment data found")

        except Exception as e:
            print(f"    Error: {e}")
            import traceback
            traceback.print_exc()

except Exception as e:
    print(f"Error running enrichment: {e}")
    import traceback
    traceback.print_exc()

# Step 4: Final count
print("\n" + "=" * 60)
print("FINAL STATUS")
print("=" * 60)
skeleton_count = DiscoveredProduct.objects.filter(status='skeleton').count()
incomplete_count = DiscoveredProduct.objects.filter(status='incomplete').count()
print(f"\nProducts after enrichment:")
print(f"  - Skeleton: {skeleton_count}")
print(f"  - Incomplete: {incomplete_count}")
