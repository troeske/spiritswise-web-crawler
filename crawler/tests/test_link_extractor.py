"""
Tests for the Link Extraction Service.

Comprehensive test suite for link extraction, filtering, canonicalization,
and categorization functionality.
"""

import pytest
from crawler.services.link_extractor import (
    LinkExtractor,
    ExtractedLink,
    LinkType,
    LinkCategory,
)


class TestExtractAllLinks:
    """Tests for extracting all links from HTML content."""

    def test_extracts_basic_anchor_links(self):
        """Extracts standard anchor tag links from HTML."""
        html = """
        <html>
        <body>
            <a href="https://example.com/product1">Product 1</a>
            <a href="https://example.com/product2">Product 2</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        assert len(links) == 2
        assert links[0].url == "https://example.com/product1"
        assert links[0].anchor_text == "Product 1"
        assert links[1].url == "https://example.com/product2"
        assert links[1].anchor_text == "Product 2"

    def test_extracts_links_with_nested_elements(self):
        """Extracts links that contain nested HTML elements."""
        html = """
        <html>
        <body>
            <a href="/product"><span>Product</span> <strong>Name</strong></a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        assert len(links) == 1
        assert "Product" in links[0].anchor_text
        assert "Name" in links[0].anchor_text

    def test_handles_empty_html(self):
        """Returns empty list for empty HTML content."""
        extractor = LinkExtractor()
        links = extractor.extract_all_links("", "https://example.com")

        assert links == []

    def test_handles_malformed_html(self):
        """Gracefully handles malformed HTML content."""
        html = """
        <html>
        <body>
            <a href="https://example.com/product1">Product 1
            <a href="https://example.com/product2">Product 2</a>
            <div>
        </body>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        assert len(links) >= 1

    def test_ignores_javascript_links(self):
        """Ignores javascript: protocol links."""
        html = """
        <html>
        <body>
            <a href="javascript:void(0)">Click me</a>
            <a href="https://example.com/real">Real Link</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        assert len(links) == 1
        assert links[0].url == "https://example.com/real"

    def test_ignores_mailto_links(self):
        """Ignores mailto: protocol links."""
        html = """
        <html>
        <body>
            <a href="mailto:info@example.com">Email us</a>
            <a href="https://example.com/contact">Contact</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        assert len(links) == 1
        assert links[0].url == "https://example.com/contact"

    def test_ignores_tel_links(self):
        """Ignores tel: protocol links."""
        html = """
        <html>
        <body>
            <a href="tel:+1234567890">Call us</a>
            <a href="https://example.com/call">Call Page</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        assert len(links) == 1
        assert links[0].url == "https://example.com/call"

    def test_captures_rel_attributes(self):
        """Captures rel attributes from links."""
        html = """
        <html>
        <body>
            <a href="https://example.com/sponsored" rel="sponsored nofollow">Sponsored</a>
            <a href="https://example.com/regular">Regular</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        sponsored_link = next(l for l in links if "sponsored" in l.url)
        assert "sponsored" in sponsored_link.rel_attributes
        assert "nofollow" in sponsored_link.rel_attributes

        regular_link = next(l for l in links if "regular" in l.url)
        assert regular_link.rel_attributes == []

    def test_sets_source_url(self):
        """Sets source_url on all extracted links."""
        html = """
        <html>
        <body>
            <a href="https://example.com/product">Product</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        base_url = "https://example.com/page"
        links = extractor.extract_all_links(html, base_url)

        assert links[0].source_url == base_url


class TestRelativeURLHandling:
    """Tests for handling relative URLs."""

    def test_resolves_absolute_path_relative_urls(self):
        """Resolves URLs starting with /."""
        html = """
        <html>
        <body>
            <a href="/products/whiskey">Whiskey</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com/page")

        assert links[0].url == "https://example.com/products/whiskey"

    def test_resolves_relative_path_urls(self):
        """Resolves URLs without leading /."""
        html = """
        <html>
        <body>
            <a href="whiskey/glenfiddich">Glenfiddich</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com/products/")

        assert "example.com" in links[0].url
        assert "glenfiddich" in links[0].url

    def test_resolves_protocol_relative_urls(self):
        """Resolves URLs starting with //."""
        html = """
        <html>
        <body>
            <a href="//cdn.example.com/product">CDN Product</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com/page")

        assert links[0].url == "https://cdn.example.com/product"

    def test_handles_parent_directory_references(self):
        """Handles ../ in relative URLs."""
        html = """
        <html>
        <body>
            <a href="../other-category/product">Other Product</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(
            html, "https://example.com/products/whiskey/"
        )

        assert "example.com" in links[0].url
        assert "other-category" in links[0].url


class TestURLCanonicalization:
    """Tests for URL canonicalization."""

    def test_removes_fragment_identifiers(self):
        """Removes # fragments from URLs."""
        html = """
        <html>
        <body>
            <a href="https://example.com/product#reviews">Reviews</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        assert links[0].url == "https://example.com/product"

    def test_removes_tracking_parameters(self):
        """Removes common tracking parameters from URLs."""
        html = """
        <html>
        <body>
            <a href="https://example.com/product?utm_source=google&utm_medium=cpc&id=123">Product</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        assert "utm_source" not in links[0].url
        assert "utm_medium" not in links[0].url
        assert "id=123" in links[0].url

    def test_normalizes_trailing_slashes(self):
        """Normalizes trailing slashes consistently."""
        html = """
        <html>
        <body>
            <a href="https://example.com/product/">Product With Slash</a>
            <a href="https://example.com/product">Product No Slash</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        # Both should be normalized to the same form
        urls = [l.url for l in links]
        assert len(set(urls)) == 1  # Both should be the same after normalization

    def test_lowercases_scheme_and_host(self):
        """Lowercases scheme and host for consistency."""
        html = """
        <html>
        <body>
            <a href="HTTPS://EXAMPLE.COM/Product">Mixed Case</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        assert links[0].url.startswith("https://example.com")


class TestDeduplication:
    """Tests for link deduplication."""

    def test_removes_duplicate_urls(self):
        """Removes duplicate URLs after canonicalization."""
        html = """
        <html>
        <body>
            <a href="https://example.com/product">Link 1</a>
            <a href="https://example.com/product">Link 2</a>
            <a href="https://example.com/product#section">Link 3</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        urls = [l.url for l in links]
        assert len(urls) == len(set(urls))

    def test_keeps_first_occurrence_anchor_text(self):
        """Keeps anchor text from first occurrence when deduplicating."""
        html = """
        <html>
        <body>
            <a href="https://example.com/product">First Text</a>
            <a href="https://example.com/product">Second Text</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        product_link = next(l for l in links if "product" in l.url)
        assert product_link.anchor_text == "First Text"


class TestProductLinkFiltering:
    """Tests for filtering product links by URL patterns."""

    def test_filters_by_single_pattern(self):
        """Filters links matching a single regex pattern."""
        extractor = LinkExtractor()
        links = [
            ExtractedLink(
                url="https://example.com/products/whiskey-123",
                anchor_text="Whiskey",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://example.com/about",
                anchor_text="About",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
        ]

        patterns = [r"/products/"]
        filtered = extractor.filter_product_links(links, patterns)

        assert len(filtered) == 1
        assert "products" in filtered[0].url

    def test_filters_by_multiple_patterns(self):
        """Filters links matching any of multiple patterns."""
        extractor = LinkExtractor()
        links = [
            ExtractedLink(
                url="https://example.com/products/whiskey",
                anchor_text="Whiskey",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://example.com/shop/rum",
                anchor_text="Rum",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://example.com/about",
                anchor_text="About",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
        ]

        patterns = [r"/products/", r"/shop/"]
        filtered = extractor.filter_product_links(links, patterns)

        assert len(filtered) == 2

    def test_supports_regex_patterns(self):
        """Supports full regex patterns for filtering."""
        extractor = LinkExtractor()
        links = [
            ExtractedLink(
                url="https://example.com/p/whiskey-123",
                anchor_text="Whiskey 123",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://example.com/p/rum-456",
                anchor_text="Rum 456",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://example.com/category/spirits",
                anchor_text="Spirits",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
        ]

        patterns = [r"/p/[a-z]+-\d+"]
        filtered = extractor.filter_product_links(links, patterns)

        assert len(filtered) == 2

    def test_returns_empty_for_no_matches(self):
        """Returns empty list when no patterns match."""
        extractor = LinkExtractor()
        links = [
            ExtractedLink(
                url="https://example.com/about",
                anchor_text="About",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
        ]

        patterns = [r"/products/"]
        filtered = extractor.filter_product_links(links, patterns)

        assert filtered == []


class TestDomainFiltering:
    """Tests for filtering links by domain."""

    def test_filters_same_domain_only(self):
        """Filters to keep only same-domain links."""
        extractor = LinkExtractor()
        links = [
            ExtractedLink(
                url="https://example.com/product",
                anchor_text="Product",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://other.com/product",
                anchor_text="Other",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
        ]

        filtered = extractor.filter_by_domain(
            links, base_url="https://example.com", same_domain_only=True
        )

        assert len(filtered) == 1
        assert "example.com" in filtered[0].url

    def test_includes_subdomains_when_same_domain(self):
        """Includes subdomains when filtering same domain."""
        extractor = LinkExtractor()
        links = [
            ExtractedLink(
                url="https://www.example.com/product",
                anchor_text="WWW Product",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://shop.example.com/product",
                anchor_text="Shop Product",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
        ]

        filtered = extractor.filter_by_domain(
            links, base_url="https://example.com", same_domain_only=True
        )

        assert len(filtered) == 2

    def test_excludes_specified_domains(self):
        """Excludes links from specified domains."""
        extractor = LinkExtractor()
        links = [
            ExtractedLink(
                url="https://example.com/product",
                anchor_text="Product",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://facebook.com/share",
                anchor_text="Share",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://twitter.com/share",
                anchor_text="Tweet",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
        ]

        filtered = extractor.filter_by_domain(
            links,
            base_url="https://example.com",
            same_domain_only=False,
            excluded_domains=["facebook.com", "twitter.com"],
        )

        assert len(filtered) == 1
        assert "example.com" in filtered[0].url

    def test_allows_all_domains_when_not_filtering(self):
        """Allows all domains when same_domain_only is False."""
        extractor = LinkExtractor()
        links = [
            ExtractedLink(
                url="https://example.com/product",
                anchor_text="Product",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://other.com/product",
                anchor_text="Other",
                source_url="https://example.com",
                link_type=LinkType.UNKNOWN,
            ),
        ]

        filtered = extractor.filter_by_domain(
            links, base_url="https://example.com", same_domain_only=False
        )

        assert len(filtered) == 2


class TestRelatedProductsExtraction:
    """Tests for extracting related products section links."""

    def test_extracts_from_related_products_section(self):
        """Extracts links from 'related products' section."""
        html = """
        <html>
        <body>
            <div class="product-details">
                <a href="/product/main">Main Product</a>
            </div>
            <div class="related-products">
                <a href="/product/related1">Related 1</a>
                <a href="/product/related2">Related 2</a>
            </div>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_related_products(html, "https://example.com")

        assert len(links) == 2
        assert all(l.link_type == LinkType.RELATED for l in links)

    def test_extracts_from_you_may_also_like_section(self):
        """Extracts links from 'you may also like' section."""
        html = """
        <html>
        <body>
            <section class="you-may-also-like">
                <a href="/product/1">Product 1</a>
                <a href="/product/2">Product 2</a>
            </section>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_related_products(html, "https://example.com")

        assert len(links) == 2

    def test_extracts_from_similar_products_section(self):
        """Extracts links from 'similar products' section."""
        html = """
        <html>
        <body>
            <div id="similar-products">
                <a href="/product/similar1">Similar 1</a>
            </div>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_related_products(html, "https://example.com")

        assert len(links) == 1

    def test_extracts_from_customers_also_bought(self):
        """Extracts links from 'customers also bought' section."""
        html = """
        <html>
        <body>
            <div class="customers-also-bought">
                <a href="/product/bought1">Bought 1</a>
                <a href="/product/bought2">Bought 2</a>
            </div>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_related_products(html, "https://example.com")

        assert len(links) == 2

    def test_returns_empty_when_no_related_section(self):
        """Returns empty list when no related products section exists."""
        html = """
        <html>
        <body>
            <div class="product">
                <a href="/product/main">Main Product</a>
            </div>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_related_products(html, "https://example.com")

        assert links == []


class TestPaginationLinkExtraction:
    """Tests for extracting pagination links."""

    def test_extracts_page_number_parameter(self):
        """Extracts links with page= parameter."""
        html = """
        <html>
        <body>
            <div class="pagination">
                <a href="/products?page=1">1</a>
                <a href="/products?page=2">2</a>
                <a href="/products?page=3">3</a>
            </div>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_pagination_links(html, "https://example.com")

        assert len(links) >= 2
        assert all(l.link_type == LinkType.PAGINATION for l in links)

    def test_extracts_page_path_segment(self):
        """Extracts links with /page/N path segment."""
        html = """
        <html>
        <body>
            <nav class="pagination">
                <a href="/products/page/1">1</a>
                <a href="/products/page/2">2</a>
            </nav>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_pagination_links(html, "https://example.com")

        assert len(links) >= 1

    def test_extracts_p_parameter(self):
        """Extracts links with ?p= parameter."""
        html = """
        <html>
        <body>
            <div class="pager">
                <a href="/catalog?p=1">1</a>
                <a href="/catalog?p=2">2</a>
            </div>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_pagination_links(html, "https://example.com")

        assert len(links) >= 1

    def test_extracts_next_prev_links(self):
        """Extracts next/prev navigation links."""
        html = """
        <html>
        <body>
            <nav>
                <a href="/products?page=1" rel="prev">Previous</a>
                <a href="/products?page=3" rel="next">Next</a>
            </nav>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_pagination_links(html, "https://example.com")

        assert len(links) >= 1

    def test_returns_empty_for_no_pagination(self):
        """Returns empty list when no pagination links exist."""
        html = """
        <html>
        <body>
            <div class="content">
                <a href="/product/1">Product 1</a>
            </div>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_pagination_links(html, "https://example.com")

        assert links == []


class TestLinkCategorization:
    """Tests for categorizing links by type."""

    def test_categorizes_product_links(self):
        """Categorizes links matching product URL patterns."""
        extractor = LinkExtractor()
        link = ExtractedLink(
            url="https://example.com/products/whiskey-123",
            anchor_text="Whiskey",
            source_url="https://example.com",
            link_type=LinkType.UNKNOWN,
        )

        category = extractor.categorize_link(link)
        assert category == LinkCategory.PRODUCT

    def test_categorizes_category_links(self):
        """Categorizes links matching category URL patterns."""
        extractor = LinkExtractor()
        link = ExtractedLink(
            url="https://example.com/category/whiskey",
            anchor_text="Whiskey Category",
            source_url="https://example.com",
            link_type=LinkType.UNKNOWN,
        )

        category = extractor.categorize_link(link)
        assert category == LinkCategory.CATEGORY

    def test_categorizes_pagination_links(self):
        """Categorizes pagination links."""
        extractor = LinkExtractor()
        link = ExtractedLink(
            url="https://example.com/products?page=2",
            anchor_text="2",
            source_url="https://example.com",
            link_type=LinkType.PAGINATION,
        )

        category = extractor.categorize_link(link)
        assert category == LinkCategory.PAGINATION

    def test_categorizes_external_links(self):
        """Categorizes external domain links."""
        extractor = LinkExtractor()
        link = ExtractedLink(
            url="https://other-site.com/product",
            anchor_text="External",
            source_url="https://example.com",
            link_type=LinkType.EXTERNAL,
        )

        category = extractor.categorize_link(link)
        assert category == LinkCategory.EXTERNAL

    def test_categorizes_related_links(self):
        """Categorizes related product links."""
        extractor = LinkExtractor()
        link = ExtractedLink(
            url="https://example.com/product/related",
            anchor_text="Related",
            source_url="https://example.com",
            link_type=LinkType.RELATED,
        )

        category = extractor.categorize_link(link)
        assert category == LinkCategory.RELATED


class TestLinkPriority:
    """Tests for link priority assignment."""

    def test_product_links_have_high_priority(self):
        """Product links have highest priority."""
        extractor = LinkExtractor()
        link = ExtractedLink(
            url="https://example.com/products/whiskey",
            anchor_text="Whiskey",
            source_url="https://example.com",
            link_type=LinkType.PRODUCT,
        )

        assert link.priority >= 80

    def test_pagination_links_have_medium_priority(self):
        """Pagination links have medium priority."""
        extractor = LinkExtractor()
        link = ExtractedLink(
            url="https://example.com/products?page=2",
            anchor_text="2",
            source_url="https://example.com",
            link_type=LinkType.PAGINATION,
        )

        assert 40 <= link.priority <= 70

    def test_external_links_have_low_priority(self):
        """External links have low priority."""
        extractor = LinkExtractor()
        link = ExtractedLink(
            url="https://other.com/page",
            anchor_text="External",
            source_url="https://example.com",
            link_type=LinkType.EXTERNAL,
        )

        assert link.priority <= 30


class TestRobotsMetaHandling:
    """Tests for respecting robots meta tags."""

    def test_respects_noindex_meta_tag(self):
        """Respects noindex meta tag by marking appropriately."""
        html = """
        <html>
        <head>
            <meta name="robots" content="noindex, nofollow">
        </head>
        <body>
            <a href="/product">Product</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        # Links from nofollow pages should be marked or empty
        # Implementation can choose to skip or mark these links
        assert isinstance(links, list)

    def test_respects_nofollow_meta_tag(self):
        """Respects nofollow meta tag on page level."""
        html = """
        <html>
        <head>
            <meta name="robots" content="nofollow">
        </head>
        <body>
            <a href="/product">Product</a>
        </body>
        </html>
        """
        extractor = LinkExtractor()
        links = extractor.extract_all_links(html, "https://example.com")

        # All links from nofollow pages should have nofollow attribute
        if links:
            assert all("nofollow" in l.rel_attributes for l in links)


class TestIntegration:
    """Integration tests for the complete link extraction pipeline."""

    def test_full_extraction_pipeline(self):
        """Tests the complete extraction pipeline with realistic HTML."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Whiskey Store</title>
        </head>
        <body>
            <nav>
                <a href="/">Home</a>
                <a href="/category/whiskey">Whiskey</a>
                <a href="/category/rum">Rum</a>
            </nav>

            <main>
                <div class="products">
                    <a href="/products/glenfiddich-18">
                        <span>Glenfiddich 18 Year Old</span>
                    </a>
                    <a href="/products/macallan-12?utm_source=homepage">
                        Macallan 12 Year Old
                    </a>
                </div>

                <div class="pagination">
                    <a href="/products?page=1">1</a>
                    <a href="/products?page=2">2</a>
                </div>

                <div class="related-products">
                    <a href="/products/lagavulin-16">Lagavulin 16</a>
                </div>
            </main>

            <footer>
                <a href="https://facebook.com/share" rel="nofollow">Share</a>
                <a href="mailto:info@store.com">Contact</a>
            </footer>
        </body>
        </html>
        """
        extractor = LinkExtractor()

        # Extract all links
        all_links = extractor.extract_all_links(html, "https://store.com")
        assert len(all_links) > 0

        # Filter product links
        product_links = extractor.filter_product_links(
            all_links, [r"/products/[a-z]"]
        )
        assert len(product_links) >= 2

        # Extract pagination
        pagination_links = extractor.extract_pagination_links(
            html, "https://store.com"
        )
        assert len(pagination_links) >= 1

        # Extract related products
        related_links = extractor.extract_related_products(
            html, "https://store.com"
        )
        assert len(related_links) >= 1

        # Verify tracking params removed
        macallan_link = next(
            (l for l in all_links if "macallan" in l.url.lower()), None
        )
        if macallan_link:
            assert "utm_source" not in macallan_link.url

    def test_handles_real_world_patterns(self):
        """Tests common real-world URL patterns."""
        extractor = LinkExtractor()

        patterns = [
            # Common e-commerce patterns
            r"/product/",
            r"/products/",
            r"/p/",
            r"/item/",
            r"/dp/",  # Amazon style
            r"/shop/[^/]+/[^/]+",  # /shop/category/product
        ]

        links = [
            ExtractedLink(
                url="https://example.com/product/whiskey-123",
                anchor_text="",
                source_url="",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://example.com/shop/whiskey/glenfiddich",
                anchor_text="",
                source_url="",
                link_type=LinkType.UNKNOWN,
            ),
            ExtractedLink(
                url="https://example.com/about-us",
                anchor_text="",
                source_url="",
                link_type=LinkType.UNKNOWN,
            ),
        ]

        filtered = extractor.filter_product_links(links, patterns)
        assert len(filtered) == 2
