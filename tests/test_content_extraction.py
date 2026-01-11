"""
TDD Tests for Content Extraction in ContentProcessor.

These tests verify that extract_content() preserves critical product information
(title, h1) even when trafilatura strips it from sparse main content pages.

RED TEST SCENARIO:
- When main product section is sparse but sidebar has detailed content
- Trafilatura may strip the <h1> and <title> containing the product name
- extract_content() should ALWAYS include title and h1 in the output

FIX:
- Extract title and h1 using BeautifulSoup
- Prepend them to the trafilatura-extracted text
"""

import pytest


# =============================================================================
# Test HTML Content
# =============================================================================

# Sparse main content with detailed sidebar (causes trafilatura to lose headings)
SPARSE_MAIN_WITH_SIDEBAR = """
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

# Standard product page (headings normally preserved)
STANDARD_PRODUCT_PAGE = """
<!DOCTYPE html>
<html>
<head><title>Glenfiddich 12 Year Old | Shop</title></head>
<body>
<div class="product">
    <h1>Glenfiddich 12 Year Old</h1>
    <p>A classic Speyside single malt whisky.</p>
    <ul>
        <li>ABV: 40%</li>
        <li>Volume: 70cl</li>
        <li>Origin: Scotland</li>
    </ul>
    <div class="description">
        <p>Fruity and fresh with subtle oak notes.</p>
    </div>
</div>
</body>
</html>
"""

# Title only (no h1)
TITLE_ONLY = """
<!DOCTYPE html>
<html>
<head><title>Macallan 18 Year Old Sherry Cask</title></head>
<body>
<div class="product-info">
    <p>Rich and complex whisky.</p>
</div>
</body>
</html>
"""

# H1 only (no title)
H1_ONLY = """
<!DOCTYPE html>
<html>
<head><title></title></head>
<body>
<h1>Talisker 10 Year Old</h1>
<p>Bold and peaty from Skye.</p>
</body>
</html>
"""


# =============================================================================
# Test Classes
# =============================================================================

class TestContentExtraction:
    """Tests for ContentProcessor.extract_content()"""

    def test_preserves_h1_when_trafilatura_strips_it(self):
        """
        RED TEST: H1 product name should be preserved even when trafilatura strips it.

        Trafilatura may strip h1 when main content is sparse and sidebar has more content.
        """
        from crawler.services.content_processor import ContentProcessor

        processor = ContentProcessor()
        extracted = processor.extract_content(SPARSE_MAIN_WITH_SIDEBAR)

        # H1 should be in extracted content
        assert "ardbeg" in extracted.lower(), \
            f"H1 'Ardbeg 10 Year Old' should be preserved. Got: {extracted[:200]}"

    def test_preserves_title_when_trafilatura_strips_it(self):
        """
        RED TEST: Title should be preserved even when trafilatura strips it.
        """
        from crawler.services.content_processor import ContentProcessor

        processor = ContentProcessor()
        extracted = processor.extract_content(SPARSE_MAIN_WITH_SIDEBAR)

        # Title should be in extracted content
        assert "ardbeg" in extracted.lower(), \
            f"Title 'Ardbeg 10 Year Old' should be preserved. Got: {extracted[:200]}"

    def test_normal_page_still_works(self):
        """
        Standard product pages should still work correctly.
        """
        from crawler.services.content_processor import ContentProcessor

        processor = ContentProcessor()
        extracted = processor.extract_content(STANDARD_PRODUCT_PAGE)

        assert "glenfiddich" in extracted.lower(), \
            f"Product name should be in extracted content. Got: {extracted[:200]}"

    def test_title_only_page(self):
        """
        Pages with title but no h1 should use title.
        """
        from crawler.services.content_processor import ContentProcessor

        processor = ContentProcessor()
        extracted = processor.extract_content(TITLE_ONLY)

        assert "macallan" in extracted.lower(), \
            f"Title 'Macallan' should be preserved. Got: {extracted[:200]}"

    def test_h1_only_page(self):
        """
        Pages with h1 but empty title should use h1.
        """
        from crawler.services.content_processor import ContentProcessor

        processor = ContentProcessor()
        extracted = processor.extract_content(H1_ONLY)

        assert "talisker" in extracted.lower(), \
            f"H1 'Talisker' should be preserved. Got: {extracted[:200]}"

    def test_sidebar_products_not_prioritized_over_main(self):
        """
        Main product (h1) should appear before sidebar products in extracted content.
        """
        from crawler.services.content_processor import ContentProcessor

        processor = ContentProcessor()
        extracted = processor.extract_content(SPARSE_MAIN_WITH_SIDEBAR)

        ardbeg_pos = extracted.lower().find("ardbeg")
        laphroaig_pos = extracted.lower().find("laphroaig")

        assert ardbeg_pos >= 0, "Ardbeg should be in extracted content"

        # If Laphroaig is present, Ardbeg should come first
        if laphroaig_pos >= 0:
            assert ardbeg_pos < laphroaig_pos, \
                f"Main product 'Ardbeg' should appear before sidebar 'Laphroaig'. " \
                f"Ardbeg at {ardbeg_pos}, Laphroaig at {laphroaig_pos}"


class TestContentExtractionEdgeCases:
    """Edge case tests for content extraction."""

    def test_handles_no_title_or_h1(self):
        """
        Pages with no title or h1 should still extract content.
        """
        from crawler.services.content_processor import ContentProcessor

        html = """
        <html><body>
        <p>This whisky is 40% ABV and has notes of vanilla.</p>
        </body></html>
        """

        processor = ContentProcessor()
        extracted = processor.extract_content(html)

        # Should still return content
        assert extracted and len(extracted) > 0

    def test_handles_empty_html(self):
        """
        Empty HTML should return empty or fall back gracefully.
        """
        from crawler.services.content_processor import ContentProcessor

        processor = ContentProcessor()
        extracted = processor.extract_content("")

        assert extracted is not None  # Shouldn't crash

    def test_handles_malformed_html(self):
        """
        Malformed HTML should not crash extraction.
        """
        from crawler.services.content_processor import ContentProcessor

        html = "<html><head><title>Test</title><body><h1>Product</h1><p>Text"

        processor = ContentProcessor()
        extracted = processor.extract_content(html)

        # Should extract something without crashing
        assert extracted is not None
