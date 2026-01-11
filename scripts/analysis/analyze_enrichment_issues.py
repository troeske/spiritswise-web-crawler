#!/usr/bin/env python
"""Analyze enrichment pipeline and PortWineDetails."""
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from django.conf import settings
from crawler.models import DiscoveredProduct, PortWineDetails

print("=" * 80)
print("ENRICHMENT PIPELINE & API KEY ANALYSIS")
print(f"Timestamp: {datetime.now().isoformat()}")
print("=" * 80)

# 1. Check API Keys from environment
print("\n[1] API KEY CONFIGURATION")
print("-" * 60)

serpapi_key = os.environ.get('SERPAPI_API_KEY', '')
scrapingbee_key = os.environ.get('SCRAPINGBEE_API_KEY', '')
ai_service_url = os.environ.get('AI_ENHANCEMENT_SERVICE_URL', '')
ai_service_token = os.environ.get('AI_ENHANCEMENT_SERVICE_TOKEN', '')

print(f"SERPAPI_API_KEY: {'SET (' + serpapi_key[:20] + '...)' if serpapi_key else 'MISSING'}")
print(f"SCRAPINGBEE_API_KEY: {'SET (' + scrapingbee_key[:20] + '...)' if scrapingbee_key else 'MISSING'}")
print(f"AI_ENHANCEMENT_SERVICE_URL: {ai_service_url or 'MISSING'}")
print(f"AI_ENHANCEMENT_SERVICE_TOKEN: {'SET' if ai_service_token else 'MISSING'}")

# 2. Check if ScrapingBee client can be initialized
print("\n[2] SCRAPINGBEE CLIENT INITIALIZATION")
print("-" * 60)

try:
    from crawler.services.scrapingbee_client import ScrapingBeeClient
    client = ScrapingBeeClient()
    print(f"ScrapingBeeClient imported successfully")
    print(f"  API Key set: {bool(client.api_key)}")
    print(f"  Base URL: {getattr(client, 'base_url', 'N/A')}")
except ImportError as e:
    print(f"IMPORT ERROR: {e}")
except Exception as e:
    print(f"INIT ERROR: {e}")

# 3. Check discovery orchestrator's client initialization
print("\n[3] DISCOVERY ORCHESTRATOR CLIENT CHECK")
print("-" * 60)

try:
    from crawler.services.discovery_orchestrator import DiscoveryOrchestrator
    orch = DiscoveryOrchestrator()

    # Check smart_crawler
    smart_crawler = getattr(orch, 'smart_crawler', None)
    print(f"SmartCrawler: {type(smart_crawler).__name__ if smart_crawler else 'None'}")

    if smart_crawler:
        # Check smart_crawler's clients
        sb_client = getattr(smart_crawler, 'scrapingbee_client', None)
        ai_client = getattr(smart_crawler, 'ai_client', None)
        print(f"  - ScrapingBee client: {type(sb_client).__name__ if sb_client else 'None'}")
        print(f"  - AI client: {type(ai_client).__name__ if ai_client else 'None'}")

    # Check serpapi client
    serpapi = getattr(orch, 'serpapi_client', None)
    print(f"SerpAPI client: {type(serpapi).__name__ if serpapi else 'None'}")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

# 4. Analyze PortWineDetails
print("\n\n[4] PORT WINE DETAILS MODEL")
print("-" * 60)

port_products = DiscoveredProduct.objects.filter(product_type='port_wine')
port_count = port_products.count()
print(f"Total port wine products: {port_count}")

port_details = PortWineDetails.objects.all()
pd_total = port_details.count()
print(f"Total PortWineDetails records: {pd_total}")

if pd_total > 0:
    with_style = port_details.exclude(style__isnull=True).exclude(style='').count()
    with_indication_age = port_details.exclude(indication_age__isnull=True).exclude(indication_age='').count()
    with_harvest = port_details.filter(harvest_year__isnull=False).count()
    with_quinta = port_details.exclude(quinta__isnull=True).exclude(quinta='').count()
    with_producer = port_details.exclude(producer_house__isnull=True).exclude(producer_house='').count()
    with_grapes = port_details.filter(grape_varieties__isnull=False).count()
    with_subregion = port_details.exclude(douro_subregion__isnull=True).exclude(douro_subregion='').count()

    print(f"\nPortWineDetails Fields Population:")
    print(f"  Style (ruby/tawny/etc): {with_style}/{pd_total} ({100*with_style//pd_total if pd_total else 0}%)")
    print(f"  Indication Age:        {with_indication_age}/{pd_total} ({100*with_indication_age//pd_total if pd_total else 0}%)")
    print(f"  Harvest Year:          {with_harvest}/{pd_total}")
    print(f"  Quinta:                {with_quinta}/{pd_total}")
    print(f"  Producer House:        {with_producer}/{pd_total}")
    print(f"  Grape Varieties:       {with_grapes}/{pd_total}")
    print(f"  Douro Subregion:       {with_subregion}/{pd_total}")

    print(f"\nSample PortWineDetails (first 5):")
    for pd in port_details[:5]:
        product_name = pd.product.name[:40] if pd.product else "NO PRODUCT"
        print(f"\n  Product: {product_name}...")
        print(f"    Style: {pd.style or 'MISSING'}")
        print(f"    Indication Age: {pd.indication_age or 'MISSING'}")
        print(f"    Quinta: {pd.quinta or 'MISSING'}")
        print(f"    Producer House: {pd.producer_house or 'MISSING'}")
else:
    print("  NO PortWineDetails records found!")

# 5. Check enrichment flow
print("\n\n[5] ENRICHMENT FLOW INVESTIGATION")
print("-" * 60)

# Check if there are any crawl jobs
from crawler.models import CrawlJob, DiscoveryJob

crawl_jobs = CrawlJob.objects.order_by('-created_at')[:5]
print(f"Recent CrawlJobs: {CrawlJob.objects.count()}")
for job in crawl_jobs:
    print(f"  - {job.id[:8]}... status={job.status} created={job.created_at}")

discovery_jobs = DiscoveryJob.objects.order_by('-started_at')[:5]
print(f"\nRecent DiscoveryJobs: {DiscoveryJob.objects.count()}")
for job in discovery_jobs:
    print(f"  - {job.id[:8]}... type={job.job_type} status={job.status}")
    if job.result:
        print(f"    Result: {str(job.result)[:100]}...")

# 6. Check product discovery_sources field for enrichment trace
print("\n\n[6] ENRICHMENT TRACE IN PRODUCTS")
print("-" * 60)

for p in DiscoveredProduct.objects.order_by('-discovered_at')[:3]:
    print(f"\nProduct: {p.name[:50]}...")
    print(f"  Status: {p.status}")
    print(f"  Discovery Source: {p.discovery_source}")
    print(f"  Source URL: {p.source_url or 'NONE'}")
    print(f"  Source Count: {p.source_count}")

    sources = p.discovery_sources
    if sources:
        print(f"  Discovery Sources: {type(sources).__name__}")
        if isinstance(sources, list):
            for s in sources[:2]:
                print(f"    - {s}")
        elif isinstance(sources, dict):
            print(f"    Keys: {list(sources.keys())}")
        else:
            print(f"    Value: {str(sources)[:80]}")
    else:
        print(f"  Discovery Sources: EMPTY")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
print("""
KEY FINDINGS:
1. API Keys configured in .env file
2. Check if ScrapingBee client initializes properly
3. Check if enrichment is being triggered for skeleton products
4. Check PortWineDetails population
""")
