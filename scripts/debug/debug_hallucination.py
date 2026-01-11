"""Debug the hallucination test to find why product name is empty."""
import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

import django
django.setup()

from crawler.services.content_processor import ContentProcessor

MOCK_CONFUSING_HTML = """
<!DOCTYPE html>
<html>
<head><title>Ardbeg 10 Year Old | The Whisky Exchange</title></head>
<body>
<div class="product-main">
    <h1 class="product-name">Ardbeg 10 Year Old</h1>
    <p>This is the product you're looking for.</p>
</div>

<!-- Sidebar with related products -->
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

print("=" * 60)
print("DEBUG: Content Extraction Test")
print("=" * 60)

processor = ContentProcessor()
extracted = processor.extract_content(MOCK_CONFUSING_HTML)

print("\nExtracted content:")
print("-" * 40)
print(extracted)
print("-" * 40)
print(f"Length: {len(extracted)}")
print(f"Contains 'Ardbeg': {'ardbeg' in extracted.lower()}")
