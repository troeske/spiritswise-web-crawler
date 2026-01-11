"""Test AI service response directly."""
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from django.conf import settings
import httpx
import json

API_KEY = getattr(settings, "AI_ENHANCEMENT_SERVICE_TOKEN", None)
print(f"API Key configured: {bool(API_KEY)}")

CONTENT = """[Page Title: Ardbeg 10 Year Old]
[Main Heading: Ardbeg 10 Year Old]
This is the product you are looking for.
You May Also Like
Laphroaig 10 Year Old
Another great Islay whisky. 40% ABV. 70cl.
Medicinal, peaty, with notes of seaweed.
Lagavulin 16 Year Old
The smoothest Islay. 43% ABV. 70cl.
Rich, smoky, with dried fruit notes."""

headers = {}
if API_KEY:
    headers["Authorization"] = f"Bearer {API_KEY}"

response = httpx.post(
    "https://api.spiritswise.tech/api/v1/enhance/from-crawler/",
    json={
        "content": CONTENT,
        "source_url": "https://www.thewhiskyexchange.com/p/66/ardbeg-10-year-old",
        "product_type_hint": "whiskey"
    },
    headers=headers,
    timeout=60.0
)

print(f"Status: {response.status_code}")
print(f"Response:\n{json.dumps(response.json(), indent=2)}")
