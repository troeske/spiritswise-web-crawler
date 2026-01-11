#!/usr/bin/env python
"""Test AI service directly with cached content."""
import os
import sys
import logging
import time

logging.disable(logging.CRITICAL)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from crawler.models import CrawledSource
from crawler.tests.integration.ai_service_client import AIEnhancementClient
from crawler.services.smart_crawler import SmartCrawler
import trafilatura
import re

print("=" * 60)
print("DIRECT AI SERVICE TEST WITH CACHED CONTENT")
print("=" * 60)

# Get cached content
source = CrawledSource.objects.filter(
    url__contains='glencadam'
).exclude(raw_content='').exclude(raw_content__isnull=True).first()

if not source:
    print("No Glencadam content found, using any cached content...")
    source = CrawledSource.objects.exclude(raw_content='').exclude(raw_content__isnull=True).first()

if not source:
    print("No cached content found!")
    sys.exit(1)

print(f"Source URL: {source.url}")
print(f"Raw content: {len(source.raw_content):,} chars")

# Use SmartCrawler's improved extraction
print("\nUsing SmartCrawler._trim_content()...")
class MockClient:
    pass
crawler = SmartCrawler(MockClient(), MockClient())
content = crawler._trim_content(source.raw_content)
print(f"Extracted: {len(content):,} chars")

print(f"\nContent preview (first 500 chars):")
print("-" * 40)
print(content[:500])
print("-" * 40)

# Test AI service
print("\nCalling AI service...")
client = AIEnhancementClient()
start = time.time()
result = client.enhance_from_crawler(
    content=content,
    source_url=source.url,
    product_type_hint='whiskey'
)
elapsed = time.time() - start

print(f"\nAI Service Response ({elapsed:.1f}s):")
print(f"  Success: {result.get('success')}")
if result.get('success'):
    data = result.get('data', {})
    print(f"  Data keys: {list(data.keys())[:10]}")

    # Check extracted_data
    extracted_data = data.get('extracted_data', {})
    print(f"\n  Extracted product:")
    print(f"    Name: {extracted_data.get('name', 'N/A')}")
    print(f"    Brand: {extracted_data.get('brand', 'N/A')}")
    print(f"    ABV: {extracted_data.get('abv', 'N/A')}")
    print(f"    Region: {extracted_data.get('region', 'N/A')}")

    # Check enrichment
    enrichment = data.get('enrichment', {})
    tasting = enrichment.get('tasting_notes', {})
    print(f"\n  Tasting notes:")
    print(f"    Nose: {tasting.get('nose', 'N/A')[:100] if tasting.get('nose') else 'N/A'}...")
    print(f"    Palate: {tasting.get('palate', 'N/A')[:100] if tasting.get('palate') else 'N/A'}...")
    print(f"    Finish: {tasting.get('finish', 'N/A')[:100] if tasting.get('finish') else 'N/A'}...")
else:
    print(f"  Error: {result.get('error', 'Unknown')}")
    print(f"  Status: {result.get('status_code')}")

print("\n" + "=" * 60)
