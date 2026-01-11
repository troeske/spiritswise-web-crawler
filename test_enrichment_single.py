"""Test enrichment flow for a single product to diagnose issues."""

import asyncio
import os
import logging
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.test')
django.setup()

from dotenv import load_dotenv
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_single_product_enrichment():
    """Test enrichment for a single whiskey product."""
    from asgiref.sync import sync_to_async
    from crawler.models import DiscoveredProduct, ProductType
    from crawler.services.ai_client_v2 import AIClientV2
    from crawler.services.scrapingbee_client import ScrapingBeeClient, ScrapingBeeMode
    from crawler.discovery.serpapi_client import SerpAPIClient

    # Get API keys
    ai_url = os.getenv("AI_ENHANCEMENT_SERVICE_URL")
    ai_token = os.getenv("AI_ENHANCEMENT_SERVICE_TOKEN")
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    scrapingbee_key = os.getenv("SCRAPINGBEE_API_KEY")

    print(f"\n=== Configuration ===")
    print(f"AI URL: {ai_url}")
    print(f"AI Token: {ai_token[:20]}..." if ai_token else "AI Token: Not set")
    print(f"SerpAPI Key: {serpapi_key[:10]}..." if serpapi_key else "SerpAPI Key: Not set")
    print(f"ScrapingBee Key: {scrapingbee_key[:10]}..." if scrapingbee_key else "ScrapingBee Key: Not set")

    # Initialize clients
    print(f"\n=== Initializing Clients ===")
    ai_client = AIClientV2(base_url=ai_url, api_key=ai_token, timeout=120.0)
    serpapi_client = SerpAPIClient(api_key=serpapi_key)
    scrapingbee_client = ScrapingBeeClient(api_key=scrapingbee_key)

    print(f"ScrapingBee mock mode: {scrapingbee_client._mock_mode}")

    # Get a whiskey product (sync_to_async for DB access)
    @sync_to_async
    def get_whiskey_product():
        return DiscoveredProduct.objects.filter(product_type=ProductType.WHISKEY).first()

    product = await get_whiskey_product()
    if not product:
        print("No whiskey products found!")
        return

    print(f"\n=== Testing Product: {product.name} ===")

    # Step 1: Search for product info
    print(f"\n--- Step 1: SerpAPI Search ---")
    query = f"{product.name} tasting notes review"
    print(f"Query: {query}")

    try:
        search_results = await serpapi_client.search(query, num_results=5)
        print(f"Found {len(search_results)} results")
        for result in search_results[:3]:
            print(f"  - {result.title[:50]}... ({result.url[:50]}...)")
    except Exception as e:
        print(f"SerpAPI error: {e}")
        search_results = []

    # Step 2: Fetch content with ScrapingBee
    print(f"\n--- Step 2: ScrapingBee Fetch ---")
    if search_results:
        # Filter out blocked domains
        BLOCKED = ["reddit.com", "facebook.com", "twitter.com"]
        valid_results = [r for r in search_results if not any(b in r.url.lower() for b in BLOCKED)]

        if valid_results:
            url = valid_results[0].url
            print(f"Fetching: {url}")

            try:
                result = scrapingbee_client.fetch(url, mode=ScrapingBeeMode.JS_RENDER)
                print(f"Success: {result.get('success')}")
                print(f"Status: {result.get('status_code')}")
                print(f"Content length: {len(result.get('content', ''))} chars")
                content = result.get('content', '')
            except Exception as e:
                print(f"ScrapingBee error: {e}")
                content = None
        else:
            print("No valid URLs after filtering blocked domains")
            content = None
    else:
        print("No search results to fetch")
        content = None

    # Step 3: AI Extraction
    print(f"\n--- Step 3: AI Extraction ---")
    if content and len(content) > 100:
        try:
            extraction_result = await ai_client.extract(
                content=content,
                source_url=url,
                product_type="whiskey",
                extraction_schema=["palate_flavors", "nose_description", "palate_description", "finish_description", "abv"],
            )

            print(f"Success: {extraction_result.success}")
            print(f"Error: {extraction_result.error}")
            print(f"Products extracted: {len(extraction_result.products)}")

            if extraction_result.products:
                p = extraction_result.products[0]
                print(f"Extracted data: {p.extracted_data}")
                print(f"palate_flavors: {p.extracted_data.get('palate_flavors')}")
        except Exception as e:
            print(f"AI extraction error: {e}")
    else:
        print("No content to extract from")

    print(f"\n=== Test Complete ===")

if __name__ == "__main__":
    asyncio.run(test_single_product_enrichment())
