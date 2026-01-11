#!/usr/bin/env python
"""Test trafilatura content extraction directly."""
import os
import sys
import logging

# Suppress all logging except errors
logging.basicConfig(level=logging.ERROR)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

import requests
import trafilatura

print("=" * 60)
print("TRAFILATURA CONTENT EXTRACTION TEST")
print("=" * 60)

# Fetch a test page
url = "https://www.thewhiskyexchange.com/p/66/ardbeg-10-year-old"
print(f"\nFetching: {url}")

try:
    response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
    raw_html = response.text
    print(f"Raw HTML size: {len(raw_html):,} chars")

    # Extract with trafilatura
    extracted = trafilatura.extract(
        raw_html,
        include_comments=False,
        include_tables=True,
        no_fallback=False,
        favor_precision=False,
        include_formatting=False,
    )

    if extracted:
        print(f"Extracted size: {len(extracted):,} chars")
        print(f"Compression ratio: {len(raw_html) / len(extracted):.1f}x")
        print(f"\nExtracted content preview (first 1000 chars):")
        print("-" * 40)
        print(extracted[:1000])
        print("-" * 40)
    else:
        print("Trafilatura returned empty result!")

except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)
