#!/usr/bin/env python
"""
Enrich skeleton products using already-cached content.

This bypasses SerpAPI and uses content we've already crawled.
"""
import os
import sys
import logging
import re
import time

# Suppress verbose logging
logging.getLogger('django.db.backends').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)
logging.getLogger('httpx').setLevel(logging.ERROR)
logging.getLogger('httpcore').setLevel(logging.ERROR)
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from crawler.models import CrawledSource, DiscoveredProduct
from crawler.tests.integration.ai_service_client import AIEnhancementClient
from crawler.services.smart_crawler import SmartCrawler


class MockClient:
    """Mock client for SmartCrawler initialization."""
    pass


def find_matching_source(product):
    """Find a cached source that might contain this product's data."""
    # Try to match by product name parts
    name_parts = product.name.lower().split()

    # Keywords to search for
    keywords = [p for p in name_parts if len(p) > 3]
    if product.brand:
        keywords.append(product.brand.name.lower())

    # Search cached sources
    sources = CrawledSource.objects.exclude(raw_content='').exclude(raw_content__isnull=True)

    best_match = None
    best_score = 0

    for source in sources:
        url = source.url.lower()
        content = source.raw_content.lower() if source.raw_content else ''

        score = 0
        for kw in keywords:
            if kw in url:
                score += 2  # URL match is strong
            if kw in content[:5000]:  # Check beginning of content
                score += 1

        # Check for product name in content
        if product.name.lower() in content:
            score += 5

        if score > best_score:
            best_score = score
            best_match = source

    return best_match, best_score


def enrich_product(product, ai_client, smart_crawler):
    """Attempt to enrich a product from cached content."""
    print(f"\n{'='*60}")
    print(f"Product: {product.name[:50]}...")

    # Find matching cached source
    source, score = find_matching_source(product)

    if not source or score < 2:
        print(f"  No matching cached source found (score: {score})")
        return False

    print(f"  Found source: {source.url[:60]}... (score: {score})")

    # Use SmartCrawler to extract clean content
    clean_content = smart_crawler._trim_content(source.raw_content)
    print(f"  Content: {len(source.raw_content):,} -> {len(clean_content):,} chars")

    if len(clean_content) < 50:
        print(f"  Content too short after extraction")
        return False

    # Call AI service
    print(f"  Calling AI service...")
    start = time.time()
    try:
        result = ai_client.enhance_from_crawler(
            content=clean_content,
            source_url=source.url,
            product_type_hint='whiskey'
        )
        elapsed = time.time() - start
        print(f"  AI response in {elapsed:.1f}s: success={result.get('success')}")

        if not result.get('success'):
            print(f"  AI error: {result.get('error', 'Unknown')}")
            return False

        data = result.get('data', {})
        extracted = data.get('extracted_data', {})
        enrichment = data.get('enrichment', {})
        tasting = enrichment.get('tasting_notes', {})

        # Update product fields
        updated = 0

        if extracted.get('abv'):
            try:
                product.abv = float(extracted['abv'])
                print(f"    ABV: {product.abv}")
                updated += 1
            except (ValueError, TypeError):
                pass

        if extracted.get('description') or enrichment.get('description'):
            desc = extracted.get('description') or enrichment.get('description')
            product.description = desc[:1000] if len(desc) > 1000 else desc
            print(f"    Description: {len(desc)} chars")
            updated += 1

        if tasting.get('nose'):
            product.nose_description = tasting['nose']
            print(f"    Nose: YES")
            updated += 1

        if tasting.get('palate'):
            product.palate_description = tasting['palate']
            print(f"    Palate: YES")
            updated += 1

        if tasting.get('finish'):
            product.finish_description = tasting['finish']
            print(f"    Finish: YES")
            updated += 1

        if extracted.get('region') or enrichment.get('region'):
            product.region = extracted.get('region') or enrichment.get('region')
            print(f"    Region: {product.region}")
            updated += 1

        if extracted.get('category'):
            product.category = extracted['category']
            print(f"    Category: {product.category}")
            updated += 1

        if updated > 0:
            # Upgrade status if we enriched anything
            if product.status == 'skeleton':
                product.status = 'incomplete'
            product.save()
            print(f"  Updated {updated} fields, status: {product.status}")
            return True
        else:
            print(f"  No fields to update from AI response")
            return False

    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 60)
    print("ENRICH FROM CACHED CONTENT")
    print("=" * 60)

    # Initialize
    ai_client = AIEnhancementClient()
    smart_crawler = SmartCrawler(MockClient(), MockClient())

    # Get skeleton products
    skeletons = list(DiscoveredProduct.objects.filter(status='skeleton'))
    print(f"\nSkeleton products to enrich: {len(skeletons)}")

    # Also try to enrich incomplete products with missing fields
    incompletes = list(DiscoveredProduct.objects.filter(status='incomplete').filter(abv=None))
    print(f"Incomplete products missing ABV: {len(incompletes)}")

    enriched_count = 0

    # Enrich skeletons first
    for product in skeletons:
        if enrich_product(product, ai_client, smart_crawler):
            enriched_count += 1

    # Then incompletes
    for product in incompletes:
        if enrich_product(product, ai_client, smart_crawler):
            enriched_count += 1

    # Final status
    print("\n" + "=" * 60)
    print("FINAL STATUS")
    print("=" * 60)
    print(f"Products enriched: {enriched_count}")
    print(f"\nProducts by status:")
    print(f"  - Skeleton: {DiscoveredProduct.objects.filter(status='skeleton').count()}")
    print(f"  - Incomplete: {DiscoveredProduct.objects.filter(status='incomplete').count()}")
    print(f"  - Complete: {DiscoveredProduct.objects.filter(status='complete').count()}")


if __name__ == '__main__':
    main()
