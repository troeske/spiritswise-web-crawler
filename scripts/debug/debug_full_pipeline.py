"""Debug full pipeline to find why product name is empty."""
import os
import sys
import asyncio

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from crawler.models import CrawlerSource, CrawlJob, DiscoveredProduct
from crawler.services.content_processor import ContentProcessor
from crawler.services.ai_client_v2 import get_ai_client_v2 as get_ai_client

MOCK_CONFUSING_HTML = """
<!DOCTYPE html>
<html>
<head><title>Ardbeg 10 Year Old | The Whisky Exchange</title></head>
<body>
<div class="product-main">
    <h1 class="product-name">Ardbeg 10 Year Old</h1>
    <p>This is the product you're looking for.</p>
</div>

<div class="sidebar">
    <h3>You May Also Like</h3>
    <div class="related-product">
        <h4>Laphroaig 10 Year Old</h4>
        <p>Another great Islay whisky. 40% ABV. 70cl.</p>
        <p>Medicinal, peaty, with notes of seaweed.</p>
    </div>
    <div class="related-product">
        <h4>Lagavulin 16 Year Old</h4>
        <p>The smoothest Islay. 43% ABV. 70cl.</p>
        <p>Rich, smoky, with dried fruit notes.</p>
    </div>
</div>
</body>
</html>
"""

async def debug_pipeline():
    print("=" * 60)
    print("DEBUG: Full Pipeline Test")
    print("=" * 60)

    processor = ContentProcessor()

    # Step 1: Test content extraction
    extracted = processor.extract_content(MOCK_CONFUSING_HTML)
    print(f"\n1. Content extraction: {len(extracted)} chars")
    print(f"   Contains 'Ardbeg': {'ardbeg' in extracted.lower()}")

    # Step 2: Test AI client directly
    ai_client = get_ai_client()
    print(f"\n2. AI Client URL: {ai_client.base_url}")

    result = await ai_client.enhance_from_crawler(
        content=extracted,
        source_url="https://www.thewhiskyexchange.com/p/66/ardbeg-10-year-old",
        product_type_hint="whiskey",
    )

    print(f"\n3. AI Response:")
    print(f"   Success: {result.success}")
    print(f"   Error: {result.error}")
    print(f"   Product Type: {result.product_type}")
    print(f"   Confidence: {result.confidence}")
    print(f"   Extracted Data: {result.extracted_data}")

    if result.extracted_data:
        print(f"\n4. Extracted name: {result.extracted_data.get('name', 'NOT FOUND')}")

if __name__ == "__main__":
    asyncio.run(debug_pipeline())
