"""Test AI service timeout behavior."""

import os
import requests
import time
from dotenv import load_dotenv

load_dotenv()

AI_URL = os.getenv("AI_ENHANCEMENT_SERVICE_URL", "https://api.spiritswise.tech")
AI_TOKEN = os.getenv("AI_ENHANCEMENT_SERVICE_TOKEN")

# Simple test content - small enough to process quickly
SIMPLE_CONTENT = """
<html>
<body>
<h1>Buffalo Trace Kentucky Straight Bourbon</h1>
<p>A smooth bourbon with notes of vanilla, caramel, and oak. ABV: 45%.</p>
<p>Distilled in Kentucky by the Buffalo Trace Distillery.</p>
<p>Tasting Notes: Sweet vanilla on the nose, followed by caramel and spice on the palate.</p>
<p>Finish: Long and warm with hints of honey.</p>
</body>
</html>
"""

# Large test content - ~50KB to test timeout
LARGE_CONTENT = SIMPLE_CONTENT + "\n" + ("This is filler text. " * 10000)

def test_extraction(content, content_name):
    """Test extraction with given content."""
    print(f"\n=== Testing {content_name} ({len(content)} chars) ===")

    payload = {
        "source_data": {
            "content": content,
            "source_url": "https://example.com/test",
            "type": "raw_html",
        },
        "product_type": "whiskey",
        "extraction_schema": ["name", "brand", "abv", "palate_flavors"],
    }

    headers = {
        "Authorization": f"Bearer {AI_TOKEN}",
        "Content-Type": "application/json",
    }

    start = time.time()
    try:
        response = requests.post(
            f"{AI_URL}/api/v2/extract/",
            json=payload,
            headers=headers,
            timeout=90,  # Client timeout
        )
        elapsed = time.time() - start

        print(f"Status: {response.status_code}")
        print(f"Time: {elapsed:.2f}s")

        if response.status_code == 200:
            data = response.json()
            print(f"Success: {data.get('success', data.get('products') is not None)}")
            if data.get("error"):
                print(f"Error: {data.get('error')}")
            if data.get("products"):
                print(f"Products: {len(data['products'])}")
                for p in data["products"][:1]:
                    print(f"  Name: {p.get('extracted_data', {}).get('name')}")
                    print(f"  ABV: {p.get('extracted_data', {}).get('abv')}")
                    print(f"  Flavors: {p.get('extracted_data', {}).get('palate_flavors')}")
        else:
            print(f"Error response: {response.text[:500]}")

    except requests.Timeout:
        elapsed = time.time() - start
        print(f"Request timed out after {elapsed:.2f}s")
    except Exception as e:
        elapsed = time.time() - start
        print(f"Error after {elapsed:.2f}s: {e}")

if __name__ == "__main__":
    print(f"AI Service: {AI_URL}")
    print(f"Token: {AI_TOKEN[:20]}..." if AI_TOKEN else "Token: Not set")

    # Test with simple content first
    test_extraction(SIMPLE_CONTENT, "Simple content")

    # Test with large content
    test_extraction(LARGE_CONTENT, "Large content (~200KB)")
