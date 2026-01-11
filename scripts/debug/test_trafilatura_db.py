#!/usr/bin/env python
"""Test trafilatura on content already in database."""
import os
import sys
import logging

logging.basicConfig(level=logging.ERROR)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

import trafilatura
from crawler.models import CrawledSource

print("=" * 60)
print("TRAFILATURA TEST ON CRAWLED CONTENT")
print("=" * 60)

# Get a crawled source with content
source = CrawledSource.objects.exclude(raw_content='').exclude(raw_content__isnull=True).first()

if not source:
    print("No crawled sources with content found!")
    sys.exit(1)

print(f"\nURL: {source.url}")
print(f"Raw content size: {len(source.raw_content):,} chars")

# Extract with trafilatura
extracted = trafilatura.extract(
    source.raw_content,
    include_comments=False,
    include_tables=True,
    no_fallback=False,
    favor_precision=False,
    include_formatting=False,
)

if extracted:
    print(f"Extracted size: {len(extracted):,} chars")
    print(f"Compression ratio: {len(source.raw_content) / len(extracted):.1f}x")
    print(f"\nExtracted content preview:")
    print("-" * 60)
    print(extracted[:2000])
    print("-" * 60)
else:
    print("Trafilatura returned empty result!")
    print("\nTrying fallback regex extraction...")
    import re
    content = source.raw_content
    # Remove scripts/styles
    content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'\s+', ' ', content)
    print(f"After regex cleanup: {len(content):,} chars")

print("\n" + "=" * 60)
