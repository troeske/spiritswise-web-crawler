#!/usr/bin/env python
"""Test improved content extraction."""
import os
import sys
import logging
import re
import json

logging.disable(logging.CRITICAL)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from crawler.models import CrawledSource

print("=" * 60)
print("IMPROVED CONTENT EXTRACTION TEST")
print("=" * 60)

# Get cached content
source = CrawledSource.objects.filter(
    url__contains='glencadam'
).exclude(raw_content='').exclude(raw_content__isnull=True).first()

if not source:
    source = CrawledSource.objects.exclude(raw_content='').exclude(raw_content__isnull=True).first()

if not source:
    print("No cached content found!")
    sys.exit(1)

html = source.raw_content
print(f"Source URL: {source.url}")
print(f"Raw content: {len(html):,} chars")

# Test 1: Check for JSON-LD
print("\n1. Checking JSON-LD structured data...")
json_ld_match = re.search(
    r'<script[^>]*type="application/ld\+json"[^>]*>(.*?)</script>',
    html,
    flags=re.DOTALL | re.IGNORECASE
)
if json_ld_match:
    try:
        data = json.loads(json_ld_match.group(1))
        if isinstance(data, list):
            data = data[0]
        print(f"   Found JSON-LD: @type={data.get('@type')}")
        if data.get('@type') == 'Product':
            print(f"   Name: {data.get('name', 'N/A')}")
            print(f"   Brand: {data.get('brand', {}).get('name', 'N/A')}")
            print(f"   Description: {data.get('description', 'N/A')[:100]}...")
    except:
        print("   JSON-LD parse failed")
else:
    print("   No JSON-LD found")

# Test 2: Check Open Graph meta tags
print("\n2. Checking Open Graph meta tags...")
og_patterns = [
    (r'<meta[^>]*property="og:title"[^>]*content="([^"]+)"', 'title'),
    (r'<meta[^>]*property="og:description"[^>]*content="([^"]+)"', 'description'),
    (r'<meta[^>]*property="og:price:amount"[^>]*content="([^"]+)"', 'price'),
]
for pattern, name in og_patterns:
    match = re.search(pattern, html, flags=re.IGNORECASE)
    if match:
        value = match.group(1)[:100]
        print(f"   {name}: {value}...")
    else:
        print(f"   {name}: NOT FOUND")

# Test 3: Check product section patterns
print("\n3. Checking product section patterns...")
product_patterns = [
    (r'<div[^>]*class="[^"]*product-single[^"]*"', 'product-single'),
    (r'<section[^>]*class="[^"]*product[^"]*"', 'product-section'),
    (r'<main[^>]*>', 'main'),
    (r'<div[^>]*class="[^"]*product-description[^"]*"', 'product-description'),
]
for pattern, name in product_patterns:
    match = re.search(pattern, html, flags=re.IGNORECASE)
    print(f"   {name}: {'FOUND' if match else 'NOT FOUND'}")

# Test 4: Use SmartCrawler extraction
print("\n4. Using SmartCrawler._extract_product_section...")
from crawler.services.smart_crawler import SmartCrawler

# Create minimal SmartCrawler instance
class MockClient:
    pass

crawler = SmartCrawler(MockClient(), MockClient())
product_content = crawler._extract_product_section(html)
if product_content:
    print(f"   Extracted: {len(product_content)} chars")
    print(f"   Preview: {product_content[:500]}...")
else:
    print("   No product section found")

# Test 5: Full trim
print("\n5. Full _trim_content result...")
trimmed = crawler._trim_content(html)
print(f"   Trimmed: {len(trimmed)} chars")
print(f"   Preview: {trimmed[:500]}...")

print("\n" + "=" * 60)
