#!/usr/bin/env python
"""Debug enrichment pipeline to find where it's failing."""
import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Set up logging to see what's happening
logging.basicConfig(level=logging.DEBUG, format='%(name)s: %(message)s')

import django
django.setup()

from crawler.models import DiscoveredProduct
from crawler.services.discovery_orchestrator_v2 import DiscoveryOrchestratorV2 as DiscoveryOrchestrator

print("=" * 60)
print("ENRICHMENT DEBUG TEST")
print("=" * 60)

# Check API keys
print("\n1. Checking API keys...")
serpapi_key = os.environ.get('SERPAPI_API_KEY', '')
scrapingbee_key = os.environ.get('SCRAPINGBEE_API_KEY', '')
print(f"   SERPAPI_API_KEY: {'SET' if serpapi_key else 'NOT SET'} ({len(serpapi_key)} chars)")
print(f"   SCRAPINGBEE_API_KEY: {'SET' if scrapingbee_key else 'NOT SET'} ({len(scrapingbee_key)} chars)")

# Get one skeleton product to enrich
print("\n2. Getting a skeleton product...")
product = DiscoveredProduct.objects.filter(status='skeleton').first()
if not product:
    print("   No skeleton products found!")
    sys.exit(1)

print(f"   Product: {product.name}")
print(f"   Status: {product.status}")
print(f"   ID: {product.id}")

# Test enrichment search
print("\n3. Testing enrichment search...")
orchestrator = DiscoveryOrchestrator()

# Check if orchestrator has the search method
if not hasattr(orchestrator, '_search_and_extract_product'):
    print("   ERROR: _search_and_extract_product method not found!")
    # Try alternative enrichment path
    if hasattr(orchestrator, 'enrich_product'):
        print("   Found enrich_product method instead")
    sys.exit(1)

# Try to search for product
search_query = f"{product.name} whiskey"
print(f"   Search query: {search_query}")

try:
    result = orchestrator._search_and_extract_product(
        product_name=product.name,
        brand=product.brand.name if product.brand else None,
        product_type=product.product_type or 'whiskey',
    )

    print("\n4. Enrichment result:")
    if result:
        for key, value in result.items():
            if value:
                val_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                print(f"   {key}: {val_str}")
    else:
        print("   No enrichment data returned")

except Exception as e:
    print(f"\n   ERROR during enrichment: {e}")
    import traceback
    traceback.print_exc()
