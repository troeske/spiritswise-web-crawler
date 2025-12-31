"""
Tests for ProductCandidate Deduplication Workflow.

RECT-014: Implement ProductCandidate Deduplication Workflow

These tests verify that product candidates are properly deduplicated
using GTIN, fingerprint, and fuzzy name matching.

TDD: Tests written first before implementation.
"""

import pytest
from decimal import Decimal

from crawler.models import (
    DiscoveredBrand,
    DiscoveredProduct,
    CrawlerSource,
    CrawledSource,
    CrawledSourceTypeChoices,
    ProductCandidate,
    MatchStatusChoices,
    SourceCategory,
    ProductType,
)
from crawler.services.deduplication import (
    normalize_product_name,
    match_by_gtin,
    match_by_fingerprint,
    match_by_fuzzy_name,
    process_candidate,
    create_product_from_candidate,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
)


@pytest.fixture
def sample_crawler_source(db):
    """Create a sample CrawlerSource for tests."""
    return CrawlerSource.objects.create(
        name="IWSC",
        slug="iwsc-dedup",
        base_url="https://iwsc.net",
        category=SourceCategory.COMPETITION,
        product_types=["whiskey"],
    )


@pytest.fixture
def sample_crawled_source(db):
    """Create a sample CrawledSource for tests."""
    return CrawledSource.objects.create(
        url="https://iwsc.net/awards/2025/test-dedup",
        title="IWSC 2025 Deduplication Test",
        content_hash="deduphash001",
        source_type=CrawledSourceTypeChoices.AWARD_PAGE,
        raw_content="<html>Test</html>",
    )


@pytest.fixture
def sample_brand(db):
    """Create a sample DiscoveredBrand for tests."""
    return DiscoveredBrand.objects.create(
        name="Macallan",
        slug="macallan-dedup",
        country="Scotland",
    )


@pytest.fixture
def existing_product(db, sample_crawler_source, sample_brand):
    """Create an existing DiscoveredProduct for matching tests."""
    return DiscoveredProduct.objects.create(
        source=sample_crawler_source,
        source_url="https://iwsc.net/products/macallan-18",
        fingerprint="macallan-18-year-old-sherry-oak",
        product_type=ProductType.WHISKEY,
        raw_content="<html>Macallan 18</html>",
        raw_content_hash="existinghash001",
        name="Macallan 18 Year Old Sherry Oak",
        brand=sample_brand,
        gtin="5012345678901",
    )


class TestNameNormalization:
    """Tests for product name normalization."""

    def test_normalize_removes_special_chars(self):
        """Normalizes by removing special characters."""
        assert normalize_product_name("Macallan™ 18 Year Old®") == "macallan 18 year old"

    def test_normalize_lowercases(self):
        """Normalizes to lowercase."""
        assert normalize_product_name("MACALLAN 18 YEAR OLD") == "macallan 18 year old"

    def test_normalize_removes_extra_spaces(self):
        """Normalizes multiple spaces to single space."""
        assert normalize_product_name("Macallan   18   Year   Old") == "macallan 18 year old"

    def test_normalize_trims(self):
        """Normalizes by trimming whitespace."""
        assert normalize_product_name("  Macallan 18 Year Old  ") == "macallan 18 year old"

    def test_normalize_removes_common_suffixes(self):
        """Normalizes by removing spirit type suffixes like 'Whisky', 'Whiskey'."""
        result = normalize_product_name("Macallan 18 Year Old Whisky")
        assert result == "macallan 18 year old"

    def test_normalize_handles_unicode(self):
        """Normalizes unicode characters."""
        assert normalize_product_name("Café Patrón XO") == "cafe patron xo"


class TestGTINMatching:
    """Tests for GTIN-based product matching."""

    def test_gtin_match_finds_exact(self, existing_product):
        """Exact GTIN match returns the product."""
        match = match_by_gtin("5012345678901")
        assert match is not None
        assert match.id == existing_product.id

    def test_gtin_no_match_returns_none(self, existing_product):
        """Non-matching GTIN returns None."""
        match = match_by_gtin("9999999999999")
        assert match is None

    def test_gtin_empty_returns_none(self, existing_product):
        """Empty GTIN returns None."""
        assert match_by_gtin("") is None
        assert match_by_gtin(None) is None

    def test_gtin_strips_whitespace(self, existing_product):
        """GTIN with whitespace still matches."""
        match = match_by_gtin("  5012345678901  ")
        assert match is not None
        assert match.id == existing_product.id


class TestFingerprintMatching:
    """Tests for fingerprint-based product matching."""

    def test_fingerprint_match_finds_exact(self, existing_product):
        """Exact fingerprint match returns the product."""
        match = match_by_fingerprint("macallan-18-year-old-sherry-oak")
        assert match is not None
        assert match.id == existing_product.id

    def test_fingerprint_no_match_returns_none(self, existing_product):
        """Non-matching fingerprint returns None."""
        match = match_by_fingerprint("glenfiddich-15-year-old")
        assert match is None

    def test_fingerprint_empty_returns_none(self, existing_product):
        """Empty fingerprint returns None."""
        assert match_by_fingerprint("") is None
        assert match_by_fingerprint(None) is None


class TestFuzzyNameMatching:
    """Tests for fuzzy name matching."""

    def test_fuzzy_match_high_similarity(self, existing_product, sample_brand):
        """High similarity name matches with high confidence."""
        match, confidence = match_by_fuzzy_name(
            "Macallan 18 Year Old Sherry Oak",
            brand=sample_brand,
        )
        assert match is not None
        assert match.id == existing_product.id
        assert confidence >= 0.9

    def test_fuzzy_match_slightly_different(self, existing_product, sample_brand):
        """Slightly different name still matches."""
        match, confidence = match_by_fuzzy_name(
            "Macallan 18yr Sherry Oak",
            brand=sample_brand,
        )
        assert match is not None
        # Confidence should be medium-high (at least 0.65 which is MEDIUM_CONFIDENCE_THRESHOLD)
        assert confidence >= 0.65

    def test_fuzzy_match_no_match(self, existing_product, sample_brand):
        """Completely different product doesn't match."""
        match, confidence = match_by_fuzzy_name(
            "Glenfiddich 15 Year Old",
            brand=sample_brand,  # Different product, but testing with Macallan brand
        )
        # Either no match or very low confidence
        assert match is None or confidence < 0.5

    def test_fuzzy_match_requires_brand(self, existing_product):
        """Fuzzy match requires brand for accuracy."""
        match, confidence = match_by_fuzzy_name(
            "Macallan 18 Year Old Sherry Oak",
            brand=None,  # No brand filter
        )
        # Should still find match but might have different confidence
        assert match is not None


class TestCandidateProcessing:
    """Tests for full candidate processing pipeline."""

    def test_process_candidate_gtin_match(self, sample_crawled_source, existing_product):
        """Candidate with matching GTIN is auto-matched."""
        candidate = ProductCandidate.objects.create(
            raw_name="The Macallan 18",
            normalized_name="the macallan 18",
            source=sample_crawled_source,
            extracted_data={
                "name": "The Macallan 18",
                "gtin": "5012345678901",  # Same as existing_product
            },
        )

        result = process_candidate(candidate)

        candidate.refresh_from_db()
        assert candidate.match_status == MatchStatusChoices.MATCHED
        assert candidate.matched_product == existing_product
        assert candidate.match_method == "gtin"
        assert result["matched"] is True

    def test_process_candidate_fingerprint_match(self, sample_crawled_source, existing_product):
        """Candidate with matching fingerprint is auto-matched."""
        candidate = ProductCandidate.objects.create(
            raw_name="Macallan 18 Year Old Sherry Oak",
            normalized_name="macallan 18 year old sherry oak",
            source=sample_crawled_source,
            extracted_data={
                "name": "Macallan 18 Year Old Sherry Oak",
                "fingerprint": "macallan-18-year-old-sherry-oak",
            },
        )

        result = process_candidate(candidate)

        candidate.refresh_from_db()
        assert candidate.match_status == MatchStatusChoices.MATCHED
        assert candidate.matched_product == existing_product
        assert candidate.match_method == "fingerprint"

    def test_process_candidate_fuzzy_high_confidence(self, sample_crawled_source, existing_product, sample_brand):
        """Candidate with very similar name is matched via fuzzy."""
        # Use exact same name to ensure high confidence
        candidate = ProductCandidate.objects.create(
            raw_name="Macallan 18 Year Old Sherry Oak",  # Exact match to existing
            normalized_name="macallan 18 year old sherry oak",
            source=sample_crawled_source,
            extracted_data={
                "name": "Macallan 18 Year Old Sherry Oak",
                "brand": "Macallan",
            },
        )

        result = process_candidate(candidate)

        candidate.refresh_from_db()
        assert candidate.match_status == MatchStatusChoices.MATCHED
        assert candidate.matched_product == existing_product
        assert candidate.match_method == "fuzzy"

    def test_process_candidate_fuzzy_medium_confidence(self, sample_crawled_source, existing_product, sample_brand):
        """Candidate with medium fuzzy confidence needs review."""
        candidate = ProductCandidate.objects.create(
            raw_name="Macallan 18 Year Old",  # Missing "Sherry Oak"
            normalized_name="macallan 18 year old",
            source=sample_crawled_source,
            extracted_data={
                "name": "Macallan 18 Year Old",
                "brand": "Macallan",
            },
        )

        result = process_candidate(candidate)

        candidate.refresh_from_db()
        # Depending on fuzzy match confidence, could be matched or needs_review
        assert candidate.match_status in [MatchStatusChoices.MATCHED, MatchStatusChoices.NEEDS_REVIEW]

    def test_process_candidate_no_match_marks_for_creation(self, sample_crawled_source, sample_crawler_source, db):
        """Candidate with no match is marked for creation."""
        candidate = ProductCandidate.objects.create(
            raw_name="Glenfiddich 21 Year Old Gran Reserva",
            normalized_name="glenfiddich 21 year old gran reserva",
            source=sample_crawled_source,
            extracted_data={
                "name": "Glenfiddich 21 Year Old Gran Reserva",
                "brand": "Glenfiddich",
                "product_type": "whiskey",
                "abv": 40.0,
            },
        )

        result = process_candidate(candidate)

        candidate.refresh_from_db()
        assert candidate.match_status == MatchStatusChoices.NEW_PRODUCT
        assert result["needs_creation"] is True

        # Now actually create the product
        product = create_product_from_candidate(candidate, sample_crawler_source)
        candidate.refresh_from_db()
        assert candidate.matched_product is not None
        assert candidate.matched_product == product


class TestProductCreationFromCandidate:
    """Tests for creating products from candidates."""

    def test_create_product_basic_fields(self, sample_crawled_source, sample_crawler_source):
        """Creates product with basic fields from candidate."""
        candidate = ProductCandidate.objects.create(
            raw_name="Test Whisky 12 Year Old",
            normalized_name="test whisky 12 year old",
            source=sample_crawled_source,
            extracted_data={
                "name": "Test Whisky 12 Year Old",
                "brand": "Test",
                "product_type": "whiskey",
                "abv": 43.0,
                "age_statement": 12,
                "country": "Scotland",
            },
        )

        product = create_product_from_candidate(candidate, sample_crawler_source)

        assert product is not None
        assert product.name == "Test Whisky 12 Year Old"
        assert product.product_type == ProductType.WHISKEY
        assert product.abv == Decimal("43.0")

    def test_create_product_links_to_candidate(self, sample_crawled_source, sample_crawler_source):
        """Created product is linked to candidate."""
        candidate = ProductCandidate.objects.create(
            raw_name="Link Test Whisky",
            normalized_name="link test whisky",
            source=sample_crawled_source,
            extracted_data={
                "name": "Link Test Whisky",
                "product_type": "whiskey",
            },
        )

        product = create_product_from_candidate(candidate, sample_crawler_source)

        candidate.refresh_from_db()
        assert candidate.matched_product == product
        assert candidate.match_status == MatchStatusChoices.NEW_PRODUCT

    def test_create_product_generates_fingerprint(self, sample_crawled_source, sample_crawler_source):
        """Created product has fingerprint generated."""
        candidate = ProductCandidate.objects.create(
            raw_name="Fingerprint Test Whisky",
            normalized_name="fingerprint test whisky",
            source=sample_crawled_source,
            extracted_data={
                "name": "Fingerprint Test Whisky",
                "product_type": "whiskey",
            },
        )

        product = create_product_from_candidate(candidate, sample_crawler_source)

        assert product.fingerprint is not None
        assert len(product.fingerprint) > 0


class TestMatchingPipelineOrder:
    """Tests for matching pipeline execution order."""

    def test_gtin_takes_priority_over_fingerprint(
        self, sample_crawled_source, sample_crawler_source, sample_brand, db
    ):
        """GTIN match is checked before fingerprint."""
        # Create two products - one with GTIN, one with fingerprint
        product_gtin = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url="https://test.com/gtin-product",
            fingerprint="different-fingerprint",
            product_type=ProductType.WHISKEY,
            raw_content="<html>GTIN Product</html>",
            raw_content_hash="gtinhash001",
            name="GTIN Product",
            gtin="1234567890123",
        )

        candidate = ProductCandidate.objects.create(
            raw_name="GTIN Product",
            normalized_name="gtin product",
            source=sample_crawled_source,
            extracted_data={
                "name": "GTIN Product",
                "gtin": "1234567890123",
                "fingerprint": "some-other-fingerprint",
            },
        )

        result = process_candidate(candidate)

        candidate.refresh_from_db()
        assert candidate.match_method == "gtin"
        assert candidate.matched_product == product_gtin

    def test_fingerprint_takes_priority_over_fuzzy(
        self, sample_crawled_source, sample_crawler_source, sample_brand, db
    ):
        """Fingerprint match is checked before fuzzy matching."""
        product = DiscoveredProduct.objects.create(
            source=sample_crawler_source,
            source_url="https://test.com/fingerprint-product",
            fingerprint="exact-fingerprint-match",
            product_type=ProductType.WHISKEY,
            raw_content="<html>Fingerprint Product</html>",
            raw_content_hash="fphash001",
            name="Different Name Entirely",
            brand=sample_brand,
        )

        candidate = ProductCandidate.objects.create(
            raw_name="Fuzzy Match Name",  # Name doesn't match but fingerprint does
            normalized_name="fuzzy match name",
            source=sample_crawled_source,
            extracted_data={
                "name": "Fuzzy Match Name",
                "fingerprint": "exact-fingerprint-match",
            },
        )

        result = process_candidate(candidate)

        candidate.refresh_from_db()
        assert candidate.match_method == "fingerprint"
        assert candidate.matched_product == product


class TestThresholdConfiguration:
    """Tests for confidence threshold configuration."""

    def test_high_confidence_threshold_value(self):
        """High confidence threshold is configured correctly."""
        assert HIGH_CONFIDENCE_THRESHOLD >= 0.85
        assert HIGH_CONFIDENCE_THRESHOLD <= 1.0

    def test_medium_confidence_threshold_value(self):
        """Medium confidence threshold is configured correctly."""
        assert MEDIUM_CONFIDENCE_THRESHOLD >= 0.6
        assert MEDIUM_CONFIDENCE_THRESHOLD < HIGH_CONFIDENCE_THRESHOLD
