#!/usr/bin/env python
"""
Task 5: Enable enrichment for existing skeleton products.

This script:
1. Enables enrichment on all competition CrawlSchedules
2. Triggers the enrich_skeletons task for existing products
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from crawler.models import CrawlSchedule, DiscoveredProduct

print("=" * 60)
print("TASK 5: Enable Enrichment for Skeleton Products")
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

    # Get skeleton products to enrich (limit to 1 for testing)
    skeletons = DiscoveredProduct.objects.filter(status='skeleton')[:1]

    print(f"\nEnriching {skeletons.count()} skeleton products...")

    for product in skeletons:
        print(f"\n  Processing: {product.name[:50]}...")
        try:
            # Try to enrich using SerpAPI search
            result = orchestrator._search_and_extract_product(
                product_name=product.name,
                brand=product.brand.name if product.brand else None,
                product_type=product.product_type or 'whiskey',
            )

            if result and result.get('success') and result.get('data'):
                data = result['data']
                print(f"    - Found enrichment data (keys: {list(data.keys())[:10]}...)")

                # Update product with enriched data
                if data.get('abv'):
                    product.abv = data['abv']
                    print(f"    - ABV: {data['abv']}")
                if data.get('description'):
                    product.description = data['description'][:500] if len(data.get('description', '')) > 500 else data.get('description')
                    print(f"    - Description: YES ({len(data['description'])} chars)")
                if data.get('nose_description'):
                    product.nose_description = data['nose_description']
                    print(f"    - Nose: YES")
                if data.get('palate_description'):
                    product.palate_description = data['palate_description']
                    print(f"    - Palate: YES")
                if data.get('finish_description'):
                    product.finish_description = data['finish_description']
                    print(f"    - Finish: YES")
                if data.get('region'):
                    product.region = data['region']
                    print(f"    - Region: {data['region']}")
                if data.get('category'):
                    product.category = data['category']
                    print(f"    - Category: {data['category']}")
                if data.get('brand'):
                    # Try to set brand
                    from crawler.services.product_saver import get_or_create_brand
                    brand_obj, _ = get_or_create_brand(data)
                    if brand_obj:
                        product.brand = brand_obj
                        print(f"    - Brand: {brand_obj.name}")

                product.status = 'incomplete'  # Upgrade from skeleton
                product.save()
                print(f"    - Status: skeleton -> incomplete")
            elif result and not result.get('success'):
                print(f"    - Enrichment failed: {result.get('reason', 'unknown')}")
            else:
                print(f"    - No enrichment data found")

        except Exception as e:
            print(f"    - Error: {e}")

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
