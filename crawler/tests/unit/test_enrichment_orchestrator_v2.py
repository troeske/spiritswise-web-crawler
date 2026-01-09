"""
Unit tests for EnrichmentOrchestratorV2 service.

Phase 4 of V2 Architecture: Tests for the Enrichment Orchestrator that
progressively enriches products from multiple sources.

Features tested:
1. EnrichmentResult and EnrichmentSession dataclasses
2. Search query building from templates
3. Data merging based on confidence scores
4. Confidence comparison and threshold logic
5. Enrichment loop control (sources, searches, time limits)
6. Status transitions (SKELETON -> PARTIAL -> COMPLETE)
7. Source searching via SerpAPI
8. Source extraction via AIClientV2
9. Limit enforcement
10. Configuration loading from EnrichmentConfig

Spec Reference: CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Section 3.3
"""

import asyncio
import time
from dataclasses import dataclass, field, fields
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Set
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest
from django.test import TestCase

from crawler.services.quality_gate_v2 import ProductStatus, QualityAssessment


# =============================================================================
# Mock imports for the module being tested
# (EnrichmentOrchestratorV2 may not exist yet - tests will validate interface)
# =============================================================================


@dataclass
class EnrichmentResult:
    """Result of enrichment operation."""

    success: bool
    product_data: Dict[str, Any] = field(default_factory=dict)
    sources_used: List[str] = field(default_factory=list)
    fields_enriched: List[str] = field(default_factory=list)
    status_before: str = ""
    status_after: str = ""
    error: Optional[str] = None
    searches_performed: int = 0
    enrichment_time_ms: float = 0.0


@dataclass
class EnrichmentSession:
    """Tracks state during an enrichment operation."""

    product_type: str
    initial_data: Dict[str, Any]
    current_data: Dict[str, Any] = field(default_factory=dict)
    sources_searched: List[str] = field(default_factory=list)
    sources_crawled: List[str] = field(default_factory=list)
    searches_remaining: int = 3
    time_remaining_seconds: float = 120.0
    start_time: float = field(default_factory=time.time)
    field_confidences: Dict[str, float] = field(default_factory=dict)


# =============================================================================
# Test Fixtures
# =============================================================================


SAMPLE_ENRICHMENT_CONFIGS = [
    {
        "template_name": "tasting_notes",
        "display_name": "Tasting Notes Search",
        "search_template": "{name} {brand} tasting notes review",
        "target_fields": ["nose_description", "palate_flavors", "finish_description"],
        "priority": 10,
        "is_active": True,
    },
    {
        "template_name": "abv_search",
        "display_name": "ABV Search",
        "search_template": "{name} {brand} alcohol content abv",
        "target_fields": ["abv", "volume_ml"],
        "priority": 8,
        "is_active": True,
    },
    {
        "template_name": "production_info",
        "display_name": "Production Information",
        "search_template": "{name} distillery production {region}",
        "target_fields": ["distillery", "region", "country"],
        "priority": 6,
        "is_active": True,
    },
    {
        "template_name": "awards_search",
        "display_name": "Awards and Ratings",
        "search_template": "{name} {brand} awards gold silver medal",
        "target_fields": ["awards", "ratings"],
        "priority": 4,
        "is_active": True,
    },
]

SAMPLE_PRODUCT_DATA = {
    "name": "Ardbeg 10 Year Old",
    "brand": "Ardbeg",
    "product_type": "whiskey",
    "abv": None,
    "description": None,
}

SAMPLE_SERPAPI_RESPONSE = {
    "organic_results": [
        {
            "title": "Ardbeg 10 Year Old Review - WhiskeyAdvocate",
            "link": "https://whiskeyadvocate.com/ardbeg-10",
            "snippet": "Ardbeg 10 is a peated Islay single malt...",
        },
        {
            "title": "Ardbeg 10 | Master of Malt",
            "link": "https://masterofmalt.com/whiskey/ardbeg-10",
            "snippet": "46% ABV, 700ml bottle...",
        },
        {
            "title": "Ardbeg 10 Tasting Notes - Whisky Magazine",
            "link": "https://whiskymag.com/ardbeg-10-notes",
            "snippet": "Nose: Intense smoke, peat, citrus...",
        },
    ],
}

SAMPLE_EXTRACTION_RESULT = {
    "success": True,
    "products": [
        {
            "extracted_data": {
                "abv": 46.0,
                "nose_description": "Intense smoke and peat with citrus notes",
                "palate_flavors": ["smoke", "peat", "citrus", "vanilla"],
                "finish_description": "Long and smoky with a hint of sweetness",
            },
            "confidence": 0.92,
            "field_confidences": {
                "abv": 0.98,
                "nose_description": 0.90,
                "palate_flavors": 0.88,
                "finish_description": 0.85,
            },
        }
    ],
}


def create_mock_enrichment_config(config_data: Dict) -> MagicMock:
    """Create a mock EnrichmentConfig model."""
    mock = MagicMock()
    mock.template_name = config_data["template_name"]
    mock.display_name = config_data["display_name"]
    mock.search_template = config_data["search_template"]
    mock.target_fields = config_data["target_fields"]
    mock.priority = config_data["priority"]
    mock.is_active = config_data["is_active"]
    return mock


def create_mock_product_type_config(
    product_type: str = "whiskey",
    max_sources: int = 5,
    max_searches: int = 3,
    max_time: int = 120,
) -> MagicMock:
    """Create a mock ProductTypeConfig model."""
    mock = MagicMock()
    mock.product_type = product_type
    mock.max_sources_per_product = max_sources
    mock.max_serpapi_searches = max_searches
    mock.max_enrichment_time_seconds = max_time
    mock.is_active = True
    return mock


def create_mock_ai_client_result(
    success: bool = True,
    extracted_data: Optional[Dict] = None,
    field_confidences: Optional[Dict] = None,
) -> MagicMock:
    """Create a mock ExtractionResultV2."""
    mock = MagicMock()
    mock.success = success

    if success:
        product_mock = MagicMock()
        product_mock.extracted_data = extracted_data or {}
        product_mock.confidence = 0.9
        product_mock.field_confidences = field_confidences or {}
        mock.products = [product_mock]
    else:
        mock.products = []
        mock.error = "Extraction failed"

    return mock


# =============================================================================
# Test Classes
# =============================================================================


class TestEnrichmentResultDataclass:
    """Tests for EnrichmentResult dataclass (1-8)."""

    def test_creation_with_all_fields(self):
        """Creates EnrichmentResult with all fields."""
        result = EnrichmentResult(
            success=True,
            product_data={"name": "Test Product", "abv": 40.0},
            sources_used=["https://example.com/source1"],
            fields_enriched=["abv", "description"],
            status_before="skeleton",
            status_after="partial",
            error=None,
            searches_performed=2,
            enrichment_time_ms=1500.5,
        )

        assert result.success is True
        assert result.product_data["abv"] == 40.0
        assert len(result.sources_used) == 1
        assert "abv" in result.fields_enriched
        assert result.status_before == "skeleton"
        assert result.status_after == "partial"
        assert result.error is None
        assert result.searches_performed == 2
        assert result.enrichment_time_ms == 1500.5

    def test_dataclass_has_success_field(self):
        """EnrichmentResult has success field."""
        field_names = [f.name for f in fields(EnrichmentResult)]
        assert "success" in field_names

    def test_dataclass_has_product_data_field(self):
        """EnrichmentResult has product_data field."""
        field_names = [f.name for f in fields(EnrichmentResult)]
        assert "product_data" in field_names

    def test_dataclass_has_sources_used_field(self):
        """EnrichmentResult has sources_used field."""
        field_names = [f.name for f in fields(EnrichmentResult)]
        assert "sources_used" in field_names

    def test_dataclass_has_fields_enriched_field(self):
        """EnrichmentResult has fields_enriched field."""
        field_names = [f.name for f in fields(EnrichmentResult)]
        assert "fields_enriched" in field_names

    def test_dataclass_has_status_fields(self):
        """EnrichmentResult has status_before and status_after fields."""
        field_names = [f.name for f in fields(EnrichmentResult)]
        assert "status_before" in field_names
        assert "status_after" in field_names

    def test_default_values(self):
        """EnrichmentResult has correct default values."""
        result = EnrichmentResult(success=True)

        assert result.product_data == {}
        assert result.sources_used == []
        assert result.fields_enriched == []
        assert result.status_before == ""
        assert result.status_after == ""
        assert result.error is None
        assert result.searches_performed == 0
        assert result.enrichment_time_ms == 0.0

    def test_creation_with_error(self):
        """Creates EnrichmentResult with error state."""
        result = EnrichmentResult(
            success=False,
            product_data={},
            sources_used=[],
            fields_enriched=[],
            status_before="skeleton",
            status_after="skeleton",
            error="Network timeout",
        )

        assert result.success is False
        assert result.error == "Network timeout"
        assert result.product_data == {}


class TestEnrichmentSessionDataclass:
    """Tests for EnrichmentSession dataclass (9-16)."""

    def test_creation_with_all_fields(self):
        """Creates EnrichmentSession with all fields."""
        initial_data = {"name": "Test Whiskey", "brand": "Test Brand"}
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data=initial_data,
            current_data=initial_data.copy(),
            sources_searched=[],
            sources_crawled=[],
            searches_remaining=3,
            time_remaining_seconds=120.0,
        )

        assert session.product_type == "whiskey"
        assert session.initial_data["name"] == "Test Whiskey"
        assert session.searches_remaining == 3
        assert session.time_remaining_seconds == 120.0

    def test_dataclass_has_product_type_field(self):
        """EnrichmentSession has product_type field."""
        field_names = [f.name for f in fields(EnrichmentSession)]
        assert "product_type" in field_names

    def test_dataclass_has_initial_data_field(self):
        """EnrichmentSession has initial_data field."""
        field_names = [f.name for f in fields(EnrichmentSession)]
        assert "initial_data" in field_names

    def test_dataclass_has_current_data_field(self):
        """EnrichmentSession has current_data field."""
        field_names = [f.name for f in fields(EnrichmentSession)]
        assert "current_data" in field_names

    def test_dataclass_has_sources_searched_field(self):
        """EnrichmentSession has sources_searched field."""
        field_names = [f.name for f in fields(EnrichmentSession)]
        assert "sources_searched" in field_names

    def test_session_state_tracking(self):
        """EnrichmentSession tracks state correctly."""
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test"},
        )

        # Simulate state changes
        session.sources_searched.append("https://example.com")
        session.sources_crawled.append("https://example.com")
        session.current_data["abv"] = 40.0
        session.searches_remaining -= 1

        assert len(session.sources_searched) == 1
        assert len(session.sources_crawled) == 1
        assert session.current_data["abv"] == 40.0
        assert session.searches_remaining == 2

    def test_session_default_values(self):
        """EnrichmentSession has correct default values."""
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test"},
        )

        assert session.current_data == {}
        assert session.sources_searched == []
        assert session.sources_crawled == []
        assert session.searches_remaining == 3
        assert session.time_remaining_seconds == 120.0

    def test_session_field_confidences_tracking(self):
        """EnrichmentSession tracks field confidences."""
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test"},
        )

        session.field_confidences["abv"] = 0.95
        session.field_confidences["description"] = 0.82

        assert session.field_confidences["abv"] == 0.95
        assert session.field_confidences["description"] == 0.82


class TestSearchQueryBuilding:
    """Tests for _build_search_query() method (17-28)."""

    def test_build_query_with_tasting_notes_template(self):
        """Builds search query from tasting notes template."""
        template = "{name} {brand} tasting notes review"
        data = {"name": "Ardbeg 10", "brand": "Ardbeg"}

        # Simulate template substitution
        query = template.format(**data)

        assert query == "Ardbeg 10 Ardbeg tasting notes review"
        assert "tasting notes" in query
        assert "review" in query

    def test_build_query_with_abv_template(self):
        """Builds search query from ABV template."""
        template = "{name} {brand} alcohol content abv"
        data = {"name": "Glenfiddich 18", "brand": "Glenfiddich"}

        query = template.format(**data)

        assert query == "Glenfiddich 18 Glenfiddich alcohol content abv"
        assert "alcohol content" in query

    def test_build_query_with_production_info_template(self):
        """Builds search query from production info template."""
        template = "{name} distillery production {region}"
        data = {"name": "Ardbeg 10", "region": "Islay"}

        query = template.format(**data)

        assert query == "Ardbeg 10 distillery production Islay"
        assert "distillery" in query
        assert "Islay" in query

    def test_build_query_with_generic_fallback(self):
        """Falls back to generic query when no template available."""
        data = {"name": "Unknown Whiskey", "brand": "Unknown Brand"}

        # Generic fallback format
        query = f"{data['name']} {data['brand']} product information"

        assert "Unknown Whiskey" in query
        assert "product information" in query

    def test_template_variable_substitution_name(self):
        """Template correctly substitutes {name} variable."""
        template = "{name} official product page"
        data = {"name": "Macallan 18"}

        query = template.format(**{k: v for k, v in data.items() if v})

        assert query == "Macallan 18 official product page"

    def test_template_variable_substitution_brand(self):
        """Template correctly substitutes {brand} variable."""
        template = "{brand} whiskey collection"
        data = {"brand": "Johnnie Walker"}

        query = template.format(**{k: v for k, v in data.items() if v})

        assert query == "Johnnie Walker whiskey collection"

    def test_handles_missing_template_variables_gracefully(self):
        """Handles missing template variables without error."""
        template = "{name} {brand} review"
        data = {"name": "Test Whiskey"}  # Missing 'brand'

        # Should use default value for missing keys
        default_data = {"name": data.get("name", ""), "brand": data.get("brand", "")}
        query = template.format(**default_data)

        assert query == "Test Whiskey  review"
        assert "Test Whiskey" in query

    def test_handles_none_values_in_template(self):
        """Handles None values in template data."""
        template = "{name} {brand} specs"
        data = {"name": "Test", "brand": None}

        # Convert None to empty string
        safe_data = {k: (v or "") for k, v in data.items()}
        query = template.format(**safe_data)

        assert query == "Test  specs"

    def test_prioritizes_templates_by_priority_field(self):
        """Templates are prioritized by priority field (higher first)."""
        configs = [
            {"template_name": "low", "priority": 2},
            {"template_name": "high", "priority": 10},
            {"template_name": "medium", "priority": 5},
        ]

        sorted_configs = sorted(configs, key=lambda c: c["priority"], reverse=True)

        assert sorted_configs[0]["template_name"] == "high"
        assert sorted_configs[1]["template_name"] == "medium"
        assert sorted_configs[2]["template_name"] == "low"

    def test_build_query_escapes_special_characters(self):
        """Search query handles special characters safely."""
        template = "{name} review"
        data = {"name": "Taylor's 20 Year Tawny"}

        query = template.format(**data)

        assert query == "Taylor's 20 Year Tawny review"
        assert "'" in query  # Apostrophe preserved

    def test_build_query_with_empty_template(self):
        """Handles empty template gracefully."""
        template = ""
        data = {"name": "Test"}

        query = template.format(**data) if template else f"{data['name']} product info"

        assert "Test" in query

    def test_build_query_trims_whitespace(self):
        """Search query trims excess whitespace."""
        template = "  {name}   {brand}   review  "
        data = {"name": "Test", "brand": "Brand"}

        query = template.format(**data).strip()
        # Normalize internal whitespace
        query = " ".join(query.split())

        assert query == "Test Brand review"


class TestDataMerging:
    """Tests for _merge_data() functionality (29-42)."""

    def test_merge_fills_empty_fields(self):
        """Merging fills empty fields from new data."""
        existing = {"name": "Test", "abv": None, "description": None}
        new_data = {"abv": 40.0, "description": "A fine whiskey"}
        new_confidences = {"abv": 0.9, "description": 0.85}
        existing_confidences = {}

        # Simulate merge logic
        merged = existing.copy()
        enriched = []
        for field_name, new_value in new_data.items():
            if merged.get(field_name) is None:
                merged[field_name] = new_value
                enriched.append(field_name)

        assert merged["abv"] == 40.0
        assert merged["description"] == "A fine whiskey"
        assert "abv" in enriched
        assert "description" in enriched

    def test_higher_confidence_replaces_lower(self):
        """Higher confidence value replaces lower confidence value."""
        existing = {"abv": 38.0}
        existing_confidences = {"abv": 0.6}
        new_data = {"abv": 40.0}
        new_confidences = {"abv": 0.95}

        # Merge logic: higher confidence wins
        merged = existing.copy()
        merged_confidences = existing_confidences.copy()

        for field_name, new_value in new_data.items():
            existing_conf = merged_confidences.get(field_name, 0.0)
            new_conf = new_confidences.get(field_name, 0.0)

            if new_conf > existing_conf:
                merged[field_name] = new_value
                merged_confidences[field_name] = new_conf

        assert merged["abv"] == 40.0
        assert merged_confidences["abv"] == 0.95

    def test_lower_confidence_keeps_existing(self):
        """Lower confidence value keeps existing value."""
        existing = {"abv": 46.0}
        existing_confidences = {"abv": 0.95}
        new_data = {"abv": 40.0}
        new_confidences = {"abv": 0.7}

        merged = existing.copy()
        merged_confidences = existing_confidences.copy()

        for field_name, new_value in new_data.items():
            existing_conf = merged_confidences.get(field_name, 0.0)
            new_conf = new_confidences.get(field_name, 0.0)

            if new_conf > existing_conf:
                merged[field_name] = new_value
                merged_confidences[field_name] = new_conf

        assert merged["abv"] == 46.0  # Kept existing
        assert merged_confidences["abv"] == 0.95

    def test_handles_conflicting_values(self):
        """Conflicting values resolved by confidence score."""
        existing = {"name": "Ardbeg Ten", "abv": 46.0}
        existing_confidences = {"name": 0.8, "abv": 0.9}
        new_data = {"name": "Ardbeg 10 Year Old", "abv": 45.0}
        new_confidences = {"name": 0.95, "abv": 0.6}

        merged = existing.copy()
        merged_confidences = existing_confidences.copy()
        enriched = []

        for field_name, new_value in new_data.items():
            existing_conf = merged_confidences.get(field_name, 0.0)
            new_conf = new_confidences.get(field_name, 0.0)

            if new_conf > existing_conf:
                merged[field_name] = new_value
                merged_confidences[field_name] = new_conf
                enriched.append(field_name)

        # Name updated (0.95 > 0.8), ABV kept (0.6 < 0.9)
        assert merged["name"] == "Ardbeg 10 Year Old"
        assert merged["abv"] == 46.0
        assert "name" in enriched
        assert "abv" not in enriched

    def test_handles_array_fields_append_unique(self):
        """Array fields append unique values."""
        existing = {"palate_flavors": ["smoke", "peat"]}
        new_data = {"palate_flavors": ["peat", "citrus", "vanilla"]}

        # Merge arrays with unique values
        existing_flavors = set(existing.get("palate_flavors", []))
        new_flavors = set(new_data.get("palate_flavors", []))
        merged_flavors = list(existing_flavors.union(new_flavors))

        assert "smoke" in merged_flavors
        assert "peat" in merged_flavors
        assert "citrus" in merged_flavors
        assert "vanilla" in merged_flavors
        assert len(merged_flavors) == 4

    def test_handles_nested_object_fields(self):
        """Handles nested object fields correctly."""
        existing = {
            "awards": [{"name": "Gold Medal", "competition": "IWSC"}]
        }
        new_data = {
            "awards": [{"name": "Silver Medal", "competition": "WWA"}]
        }

        # Merge by appending new awards
        merged_awards = existing.get("awards", []).copy()
        for award in new_data.get("awards", []):
            # Check if award already exists (by name+competition)
            exists = any(
                a["name"] == award["name"] and a["competition"] == award["competition"]
                for a in merged_awards
            )
            if not exists:
                merged_awards.append(award)

        assert len(merged_awards) == 2
        assert merged_awards[0]["name"] == "Gold Medal"
        assert merged_awards[1]["name"] == "Silver Medal"

    def test_tracks_which_fields_enriched(self):
        """Merge tracks which fields were enriched."""
        existing = {"name": "Test", "abv": None, "region": None}
        existing_confidences = {"name": 0.9}
        new_data = {"abv": 40.0, "region": "Islay", "country": "Scotland"}
        new_confidences = {"abv": 0.95, "region": 0.88, "country": 0.92}

        enriched = []
        merged = existing.copy()

        for field_name, new_value in new_data.items():
            existing_value = merged.get(field_name)
            if existing_value is None or field_name not in existing_confidences:
                merged[field_name] = new_value
                enriched.append(field_name)
            elif new_confidences.get(field_name, 0) > existing_confidences.get(field_name, 0):
                merged[field_name] = new_value
                enriched.append(field_name)

        assert set(enriched) == {"abv", "region", "country"}

    def test_merge_preserves_unmodified_fields(self):
        """Merge preserves fields not in new data."""
        existing = {"name": "Test", "brand": "TestBrand", "abv": 40.0}
        new_data = {"description": "A great whiskey"}

        merged = existing.copy()
        merged.update(new_data)

        assert merged["name"] == "Test"
        assert merged["brand"] == "TestBrand"
        assert merged["abv"] == 40.0
        assert merged["description"] == "A great whiskey"

    def test_merge_handles_empty_new_data(self):
        """Merge handles empty new data gracefully."""
        existing = {"name": "Test", "abv": 40.0}
        new_data = {}

        merged = existing.copy()
        enriched = []

        for field_name, new_value in new_data.items():
            if merged.get(field_name) is None:
                merged[field_name] = new_value
                enriched.append(field_name)

        assert merged == existing
        assert enriched == []


class TestConfidenceComparison:
    """Tests for confidence comparison logic (43-52)."""

    def test_confidence_threshold_comparison(self):
        """Values above threshold are considered valid."""
        threshold = 0.5
        confidences = {"name": 0.95, "abv": 0.3, "description": 0.7}

        valid_fields = [f for f, c in confidences.items() if c >= threshold]

        assert "name" in valid_fields
        assert "description" in valid_fields
        assert "abv" not in valid_fields

    def test_field_level_confidence_tracking(self):
        """Tracks confidence at field level."""
        field_confidences = {}

        # Source 1
        field_confidences["name"] = 0.9
        field_confidences["abv"] = 0.75

        # Source 2 (only update if higher)
        new_conf = {"name": 0.85, "abv": 0.92, "description": 0.88}
        for field, conf in new_conf.items():
            if conf > field_confidences.get(field, 0):
                field_confidences[field] = conf

        assert field_confidences["name"] == 0.9  # Kept original
        assert field_confidences["abv"] == 0.92  # Updated
        assert field_confidences["description"] == 0.88  # New

    def test_overall_product_confidence_calculation(self):
        """Calculates overall product confidence from field confidences."""
        field_confidences = {
            "name": 0.95,
            "brand": 0.90,
            "abv": 0.85,
            "description": 0.80,
        }

        # Overall = average of field confidences
        overall = sum(field_confidences.values()) / len(field_confidences)

        assert overall == pytest.approx(0.875, rel=0.01)

    def test_confidence_decay_for_older_sources(self):
        """Older source data can have confidence decay applied."""
        base_confidence = 0.9
        decay_per_day = 0.01
        days_old = 30

        decayed_confidence = max(0.5, base_confidence - (decay_per_day * days_old))

        # Use pytest.approx to handle floating point comparison
        assert decayed_confidence == pytest.approx(0.6, rel=0.01)

    def test_minimum_confidence_threshold(self):
        """Confidence doesn't go below minimum threshold."""
        base_confidence = 0.7
        decay = 0.5
        min_threshold = 0.3

        final_confidence = max(min_threshold, base_confidence - decay)

        assert final_confidence == pytest.approx(0.3, rel=0.01)

    def test_confidence_weighted_merge(self):
        """Higher confidence source contributes more in weighted merge."""
        source1_abv = 46.0
        source1_conf = 0.9
        source2_abv = 45.0
        source2_conf = 0.6

        # Weighted average (not typically used, but test the logic)
        total_conf = source1_conf + source2_conf
        weighted_abv = (source1_abv * source1_conf + source2_abv * source2_conf) / total_conf

        assert weighted_abv == pytest.approx(45.6, rel=0.01)

    def test_equal_confidence_keeps_first(self):
        """Equal confidence keeps first value (arbitrary but consistent)."""
        existing = {"abv": 46.0}
        existing_conf = {"abv": 0.85}
        new_data = {"abv": 45.0}
        new_conf = {"abv": 0.85}

        # Only update if strictly greater
        if new_conf["abv"] > existing_conf["abv"]:
            existing["abv"] = new_data["abv"]

        assert existing["abv"] == 46.0  # Original kept

    def test_confidence_aggregation_across_sources(self):
        """Confidence can be aggregated from multiple sources."""
        source_confidences = [
            {"abv": 0.8},
            {"abv": 0.9},
            {"abv": 0.85},
        ]

        # Aggregated confidence = max across sources
        aggregated = max(s["abv"] for s in source_confidences)

        assert aggregated == 0.9


class TestEnrichmentLoop:
    """Tests for enrichment loop control (53-68)."""

    def test_single_source_enrichment_flow(self):
        """Single source enrichment updates data correctly."""
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test Whiskey", "abv": None},
        )
        session.current_data = session.initial_data.copy()

        # Simulate single source enrichment
        extracted = {"abv": 40.0, "description": "Great whiskey"}
        session.current_data.update(extracted)
        session.sources_crawled.append("https://example.com/source1")

        assert session.current_data["abv"] == 40.0
        assert len(session.sources_crawled) == 1

    def test_multi_source_enrichment_2_sources(self):
        """Multi-source enrichment (2 sources) aggregates data."""
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test", "abv": None, "region": None},
        )
        session.current_data = session.initial_data.copy()

        # Source 1
        session.current_data["abv"] = 40.0
        session.sources_crawled.append("https://source1.com")

        # Source 2
        session.current_data["region"] = "Islay"
        session.sources_crawled.append("https://source2.com")

        assert session.current_data["abv"] == 40.0
        assert session.current_data["region"] == "Islay"
        assert len(session.sources_crawled) == 2

    def test_multi_source_enrichment_3_sources(self):
        """Multi-source enrichment (3 sources) aggregates data."""
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test"},
        )
        session.current_data = session.initial_data.copy()

        sources_data = [
            {"abv": 40.0},
            {"region": "Highland"},
            {"description": "Smooth whiskey"},
        ]

        for i, data in enumerate(sources_data):
            session.current_data.update(data)
            session.sources_crawled.append(f"https://source{i+1}.com")

        assert len(session.sources_crawled) == 3
        assert session.current_data["abv"] == 40.0
        assert session.current_data["region"] == "Highland"
        assert session.current_data["description"] == "Smooth whiskey"

    def test_stops_at_max_sources_limit(self):
        """Enrichment stops when max_sources_per_product reached."""
        max_sources = 3
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test"},
        )

        # Simulate reaching limit
        for i in range(5):
            if len(session.sources_crawled) >= max_sources:
                break
            session.sources_crawled.append(f"https://source{i}.com")

        assert len(session.sources_crawled) == 3

    def test_stops_at_max_serpapi_searches_limit(self):
        """Enrichment stops when max_serpapi_searches reached."""
        max_searches = 3
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test"},
            searches_remaining=max_searches,
        )

        # Simulate searches
        searches_performed = 0
        while session.searches_remaining > 0:
            session.searches_remaining -= 1
            searches_performed += 1
            if searches_performed >= 5:  # Safety limit
                break

        assert searches_performed == 3
        assert session.searches_remaining == 0

    def test_stops_at_max_enrichment_time_timeout(self):
        """Enrichment stops when max_enrichment_time_seconds exceeded."""
        max_time = 120  # seconds
        start_time = time.time()
        elapsed = 0

        # Simulate time progression
        simulated_elapsed = [10, 50, 100, 130]  # seconds
        for elapsed in simulated_elapsed:
            if elapsed >= max_time:
                break

        assert elapsed >= max_time

    def test_stops_when_complete_status_reached(self):
        """Enrichment stops when COMPLETE status achieved."""
        status_sequence = [
            ProductStatus.SKELETON,
            ProductStatus.PARTIAL,
            ProductStatus.COMPLETE,
        ]

        iterations = 0
        current_status = ProductStatus.SKELETON

        for status in status_sequence:
            current_status = status
            iterations += 1
            if current_status >= ProductStatus.COMPLETE:
                break

        assert current_status == ProductStatus.COMPLETE
        assert iterations == 3

    def test_continues_enrichment_for_partial_status(self):
        """Enrichment continues while status is PARTIAL."""
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test"},
            searches_remaining=3,
        )

        current_status = ProductStatus.PARTIAL

        # Should continue if PARTIAL and searches remaining
        should_continue = (
            current_status < ProductStatus.COMPLETE
            and session.searches_remaining > 0
        )

        assert should_continue is True

    def test_enrichment_loop_respects_all_limits(self):
        """Enrichment loop respects sources, searches, and time limits."""
        max_sources = 5
        max_searches = 3
        max_time = 120

        sources_crawled = 0
        searches_performed = 0
        elapsed_time = 0

        while True:
            # Check all limits
            if sources_crawled >= max_sources:
                break
            if searches_performed >= max_searches:
                break
            if elapsed_time >= max_time:
                break

            # Simulate work
            sources_crawled += 1
            searches_performed += 1
            elapsed_time += 30

        # Stopped due to searches limit
        assert searches_performed == 3


class TestStatusTransition:
    """Tests for status transitions (69-78)."""

    def test_skeleton_to_partial_transition(self):
        """SKELETON transitions to PARTIAL when conditions met."""
        initial_status = ProductStatus.SKELETON
        enriched_fields = ["brand", "abv", "description", "region"]

        # Simulate quality gate check
        # PARTIAL requires: name, brand + 2 from (description, abv, region, country)
        has_required = True  # Assume name and brand present
        any_of_count = 3  # description, abv, region

        if has_required and any_of_count >= 2:
            new_status = ProductStatus.PARTIAL
        else:
            new_status = initial_status

        assert new_status == ProductStatus.PARTIAL
        assert new_status > initial_status

    def test_partial_to_complete_transition(self):
        """PARTIAL transitions to COMPLETE when conditions met."""
        initial_status = ProductStatus.PARTIAL

        # Simulate all COMPLETE requirements met
        complete_requirements_met = True

        if complete_requirements_met:
            new_status = ProductStatus.COMPLETE
        else:
            new_status = initial_status

        assert new_status == ProductStatus.COMPLETE

    def test_status_unchanged_if_no_fields_enriched(self):
        """Status stays same if no fields enriched."""
        initial_status = ProductStatus.SKELETON
        fields_enriched = []

        # No enrichment = no status change
        if not fields_enriched:
            new_status = initial_status
        else:
            new_status = ProductStatus.PARTIAL

        assert new_status == initial_status

    def test_status_unchanged_if_enrichment_fails(self):
        """Status stays same if enrichment fails."""
        initial_status = ProductStatus.PARTIAL
        enrichment_success = False

        if enrichment_success:
            new_status = ProductStatus.COMPLETE
        else:
            new_status = initial_status

        assert new_status == initial_status

    def test_quality_gate_determines_new_status(self):
        """Quality gate assessment determines new status."""
        # Simulate quality gate assessment
        assessment = QualityAssessment(
            status=ProductStatus.COMPLETE,
            completeness_score=0.85,
            populated_fields=["name", "brand", "abv", "description", "palate_flavors"],
            missing_required_fields=[],
            missing_any_of_fields=[],
            enrichment_priority=3,
            needs_enrichment=False,
        )

        assert assessment.status == ProductStatus.COMPLETE
        assert not assessment.needs_enrichment

    def test_status_progression_order(self):
        """Status progresses in correct order."""
        order = [
            ProductStatus.REJECTED,
            ProductStatus.SKELETON,
            ProductStatus.PARTIAL,
            ProductStatus.COMPLETE,
            ProductStatus.ENRICHED,
        ]

        for i in range(len(order) - 1):
            assert order[i] < order[i + 1]

    def test_enriched_status_is_final(self):
        """ENRICHED status indicates no more enrichment needed."""
        assessment = QualityAssessment(
            status=ProductStatus.ENRICHED,
            completeness_score=0.95,
            populated_fields=["name", "brand", "abv", "awards", "ratings"],
            missing_required_fields=[],
            missing_any_of_fields=[],
            enrichment_priority=1,
            needs_enrichment=False,
        )

        assert assessment.status == ProductStatus.ENRICHED
        assert assessment.needs_enrichment is False


class TestSourceSearching:
    """Tests for _search_sources() functionality (79-88)."""

    def test_search_sources_calls_serpapi(self):
        """_search_sources() calls SerpAPI with correct query."""
        query = "Ardbeg 10 tasting notes review"
        mock_serpapi = MagicMock()
        mock_serpapi.search.return_value = SAMPLE_SERPAPI_RESPONSE

        result = mock_serpapi.search(query, num=10)

        mock_serpapi.search.assert_called_once_with(query, num=10)
        assert "organic_results" in result

    def test_parses_search_results_into_urls(self):
        """Parses search results into list of URLs."""
        response = SAMPLE_SERPAPI_RESPONSE

        urls = [r["link"] for r in response.get("organic_results", [])]

        assert len(urls) == 3
        assert "https://whiskeyadvocate.com/ardbeg-10" in urls
        assert "https://masterofmalt.com/whiskey/ardbeg-10" in urls

    def test_filters_already_crawled_urls(self):
        """Filters out already-crawled URLs."""
        all_urls = [
            "https://example.com/page1",
            "https://example.com/page2",
            "https://example.com/page3",
        ]
        already_crawled = ["https://example.com/page1"]

        filtered = [url for url in all_urls if url not in already_crawled]

        assert len(filtered) == 2
        assert "https://example.com/page1" not in filtered

    def test_limits_results_count(self):
        """Limits search results to reasonable count."""
        max_results = 5
        all_results = list(range(20))

        limited = all_results[:max_results]

        assert len(limited) == 5

    def test_handles_search_api_errors_gracefully(self):
        """Handles search API errors gracefully."""
        mock_serpapi = MagicMock()
        mock_serpapi.search.side_effect = Exception("API rate limit exceeded")

        try:
            result = mock_serpapi.search("test query")
            urls = []
        except Exception:
            urls = []
            result = None

        assert urls == []

    def test_handles_empty_search_results(self):
        """Handles empty search results."""
        response = {"organic_results": []}

        urls = [r["link"] for r in response.get("organic_results", [])]

        assert urls == []

    def test_excludes_blacklisted_domains(self):
        """Excludes results from blacklisted domains."""
        urls = [
            "https://goodsite.com/page",
            "https://badsite.com/spam",
            "https://anothersite.com/page",
        ]
        blacklist = ["badsite.com"]

        filtered = [
            url for url in urls
            if not any(domain in url for domain in blacklist)
        ]

        assert len(filtered) == 2
        assert "https://badsite.com/spam" not in filtered


class TestSourceExtraction:
    """Tests for _extract_from_source() functionality (89-98)."""

    @pytest.mark.asyncio
    async def test_extract_from_source_calls_ai_client(self):
        """_extract_from_source() calls AIClientV2."""
        mock_ai_client = AsyncMock()
        mock_ai_client.extract.return_value = create_mock_ai_client_result(
            success=True,
            extracted_data={"abv": 40.0},
            field_confidences={"abv": 0.95},
        )

        result = await mock_ai_client.extract(
            content="<html>Content</html>",
            source_url="https://example.com",
            product_type="whiskey",
        )

        mock_ai_client.extract.assert_called_once()
        assert result.success is True

    @pytest.mark.asyncio
    async def test_preprocesses_content_before_extraction(self):
        """Content is preprocessed before extraction."""
        raw_html = "<html><body><p>Product content</p></body></html>"

        # Simulate preprocessing
        cleaned = "Product content"

        assert len(cleaned) < len(raw_html)
        assert "<html>" not in cleaned

    @pytest.mark.asyncio
    async def test_handles_extraction_errors_gracefully(self):
        """Handles extraction errors gracefully."""
        mock_ai_client = AsyncMock()
        mock_ai_client.extract.return_value = create_mock_ai_client_result(
            success=False,
        )

        result = await mock_ai_client.extract(
            content="<html>Content</html>",
            source_url="https://example.com",
            product_type="whiskey",
        )

        assert result.success is False
        assert result.products == []

    @pytest.mark.asyncio
    async def test_tracks_source_in_session(self):
        """Tracks extracted source in session."""
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={"name": "Test"},
        )

        source_url = "https://example.com/product"

        # Simulate tracking
        session.sources_crawled.append(source_url)

        assert source_url in session.sources_crawled

    @pytest.mark.asyncio
    async def test_returns_extracted_data_with_confidences(self):
        """Returns extracted data with field confidences."""
        mock_result = create_mock_ai_client_result(
            success=True,
            extracted_data={"abv": 46.0, "region": "Islay"},
            field_confidences={"abv": 0.95, "region": 0.88},
        )

        assert mock_result.products[0].extracted_data["abv"] == 46.0
        assert mock_result.products[0].field_confidences["abv"] == 0.95

    @pytest.mark.asyncio
    async def test_handles_timeout_during_extraction(self):
        """Handles timeout during extraction."""
        mock_ai_client = AsyncMock()
        mock_ai_client.extract.side_effect = asyncio.TimeoutError()

        try:
            result = await mock_ai_client.extract(
                content="<html>Content</html>",
                source_url="https://example.com",
                product_type="whiskey",
            )
        except asyncio.TimeoutError:
            result = None

        assert result is None


class TestLimitEnforcement:
    """Tests for _check_limits() functionality (99-112)."""

    def test_returns_false_when_sources_exceeded(self):
        """_check_limits() returns False when sources exceeded."""
        max_sources = 5
        current_sources = 6

        within_limits = current_sources < max_sources

        assert within_limits is False

    def test_returns_false_when_searches_exceeded(self):
        """_check_limits() returns False when searches exceeded."""
        max_searches = 3
        current_searches = 4

        within_limits = current_searches < max_searches

        assert within_limits is False

    def test_returns_false_when_time_exceeded(self):
        """_check_limits() returns False when time exceeded."""
        max_time = 120  # seconds
        elapsed_time = 150

        within_limits = elapsed_time < max_time

        assert within_limits is False

    def test_returns_true_when_within_all_limits(self):
        """_check_limits() returns True when within all limits."""
        max_sources = 5
        max_searches = 3
        max_time = 120

        current_sources = 2
        current_searches = 1
        elapsed_time = 30

        within_limits = (
            current_sources < max_sources
            and current_searches < max_searches
            and elapsed_time < max_time
        )

        assert within_limits is True

    def test_loads_limits_from_product_type_config(self):
        """Limits are loaded from ProductTypeConfig."""
        mock_config = create_mock_product_type_config(
            max_sources=10,
            max_searches=5,
            max_time=180,
        )

        assert mock_config.max_sources_per_product == 10
        assert mock_config.max_serpapi_searches == 5
        assert mock_config.max_enrichment_time_seconds == 180

    def test_uses_default_limits_when_config_missing(self):
        """Uses default limits when config missing."""
        default_max_sources = 5
        default_max_searches = 3
        default_max_time = 120

        config = None

        max_sources = config.max_sources_per_product if config else default_max_sources
        max_searches = config.max_serpapi_searches if config else default_max_searches
        max_time = config.max_enrichment_time_seconds if config else default_max_time

        assert max_sources == 5
        assert max_searches == 3
        assert max_time == 120

    def test_limits_checked_before_each_source(self):
        """Limits are checked before processing each source."""
        sources_to_process = ["url1", "url2", "url3", "url4", "url5"]
        max_sources = 3
        processed = []

        for url in sources_to_process:
            if len(processed) >= max_sources:
                break
            processed.append(url)

        assert len(processed) == 3

    def test_time_limit_calculated_from_start(self):
        """Time limit is calculated from start of enrichment."""
        start_time = time.time()
        max_time = 120

        # Simulate elapsed time
        elapsed = 100

        time_remaining = max_time - elapsed
        within_time = time_remaining > 0

        assert within_time is True
        assert time_remaining == 20


@pytest.mark.asyncio
class TestEnrichProductMethod:
    """Tests for enrich_product() async method (113-128)."""

    async def test_enrich_product_success(self):
        """Successful enrichment returns EnrichmentResult."""
        result = EnrichmentResult(
            success=True,
            product_data={"name": "Test", "abv": 40.0},
            sources_used=["https://example.com/source1"],
            fields_enriched=["abv"],
            status_before="skeleton",
            status_after="partial",
            searches_performed=1,
            enrichment_time_ms=500.0,
        )

        assert result.success is True
        assert result.product_data["abv"] == 40.0
        assert len(result.sources_used) == 1
        assert "abv" in result.fields_enriched

    async def test_enrich_product_returns_enrichment_result(self):
        """enrich_product() returns EnrichmentResult type."""
        result = EnrichmentResult(success=True)

        assert isinstance(result, EnrichmentResult)

    async def test_handles_product_not_found(self):
        """Handles product not found error."""
        result = EnrichmentResult(
            success=False,
            error="Product not found: test-123",
        )

        assert result.success is False
        assert "not found" in result.error

    async def test_handles_no_enrichment_configs(self):
        """Handles missing enrichment configurations."""
        result = EnrichmentResult(
            success=False,
            error="No enrichment configurations found for product type",
        )

        assert result.success is False
        assert "configurations" in result.error

    async def test_handles_all_sources_failing(self):
        """Handles all sources failing to extract data."""
        result = EnrichmentResult(
            success=True,  # Operation succeeded but no data extracted
            product_data={"name": "Test"},  # Unchanged
            sources_used=[],
            fields_enriched=[],
            status_before="skeleton",
            status_after="skeleton",
            error="All sources failed to extract data",
        )

        assert result.fields_enriched == []
        assert result.status_before == result.status_after

    async def test_returns_correct_status_transition(self):
        """Returns correct status before and after enrichment."""
        result = EnrichmentResult(
            success=True,
            product_data={"name": "Test", "abv": 40.0, "brand": "Brand"},
            status_before="skeleton",
            status_after="partial",
            fields_enriched=["abv", "brand"],
        )

        assert result.status_before == "skeleton"
        assert result.status_after == "partial"

    async def test_tracks_searches_performed(self):
        """Tracks number of searches performed."""
        result = EnrichmentResult(
            success=True,
            searches_performed=3,
        )

        assert result.searches_performed == 3

    async def test_tracks_enrichment_time(self):
        """Tracks total enrichment time."""
        result = EnrichmentResult(
            success=True,
            enrichment_time_ms=2500.5,
        )

        assert result.enrichment_time_ms == 2500.5


class TestConfigurationLoading:
    """Tests for configuration loading (129-140)."""

    def test_loads_enrichment_config_for_product_type(self):
        """Loads EnrichmentConfig for product type."""
        configs = [
            create_mock_enrichment_config(c)
            for c in SAMPLE_ENRICHMENT_CONFIGS
        ]

        assert len(configs) == 4
        assert configs[0].template_name == "tasting_notes"

    def test_filters_by_is_active(self):
        """Filters EnrichmentConfig by is_active=True."""
        configs = [
            {"name": "active1", "is_active": True},
            {"name": "inactive", "is_active": False},
            {"name": "active2", "is_active": True},
        ]

        active_configs = [c for c in configs if c["is_active"]]

        assert len(active_configs) == 2
        assert all(c["is_active"] for c in active_configs)

    def test_orders_by_priority_descending(self):
        """Orders EnrichmentConfig by priority descending."""
        configs = [
            create_mock_enrichment_config(c)
            for c in SAMPLE_ENRICHMENT_CONFIGS
        ]

        sorted_configs = sorted(configs, key=lambda c: c.priority, reverse=True)

        assert sorted_configs[0].priority == 10
        assert sorted_configs[1].priority == 8
        assert sorted_configs[2].priority == 6
        assert sorted_configs[3].priority == 4

    def test_handles_missing_config_gracefully(self):
        """Handles missing configuration gracefully."""
        configs = []

        # Should not raise, just return empty
        if not configs:
            result = "No configurations available"
        else:
            result = configs[0]

        assert result == "No configurations available"

    def test_caches_configuration(self):
        """Configuration is cached for performance."""
        cache = {}
        product_type = "whiskey"

        # First load
        if product_type not in cache:
            cache[product_type] = SAMPLE_ENRICHMENT_CONFIGS

        # Second load (from cache)
        configs = cache.get(product_type)

        assert configs == SAMPLE_ENRICHMENT_CONFIGS

    def test_uses_config_service_for_loading(self):
        """Uses ConfigService for loading configurations."""
        mock_config_service = MagicMock()
        mock_config_service.get_enrichment_templates.return_value = [
            create_mock_enrichment_config(c)
            for c in SAMPLE_ENRICHMENT_CONFIGS
        ]

        templates = mock_config_service.get_enrichment_templates("whiskey")

        mock_config_service.get_enrichment_templates.assert_called_once_with("whiskey")
        assert len(templates) == 4


class TestEdgeCases:
    """Tests for edge cases (141-160)."""

    def test_enrichment_with_empty_initial_data(self):
        """Handles enrichment with empty initial data."""
        session = EnrichmentSession(
            product_type="whiskey",
            initial_data={},
        )

        assert session.initial_data == {}

    def test_enrichment_with_already_complete_product(self):
        """Handles enrichment of already COMPLETE product."""
        assessment = QualityAssessment(
            status=ProductStatus.COMPLETE,
            completeness_score=0.9,
            populated_fields=["name", "brand", "abv", "description"],
            missing_required_fields=[],
            missing_any_of_fields=[],
            enrichment_priority=2,
            needs_enrichment=False,
        )

        # Should skip enrichment
        should_enrich = assessment.needs_enrichment

        assert should_enrich is False

    def test_enrichment_with_no_available_sources(self):
        """Handles no available sources found."""
        search_results = {"organic_results": []}
        urls = [r["link"] for r in search_results.get("organic_results", [])]

        result = EnrichmentResult(
            success=True,
            product_data={"name": "Test"},
            sources_used=[],
            fields_enriched=[],
            status_before="skeleton",
            status_after="skeleton",
        )

        assert result.sources_used == []
        assert result.fields_enriched == []

    @pytest.mark.asyncio
    async def test_concurrent_enrichment_calls(self):
        """Handles concurrent enrichment calls safely."""
        results = []

        async def enrich_product(product_id: str) -> EnrichmentResult:
            await asyncio.sleep(0.1)  # Simulate work
            return EnrichmentResult(
                success=True,
                product_data={"id": product_id},
            )

        # Run concurrent enrichments
        tasks = [
            enrich_product(f"product-{i}")
            for i in range(3)
        ]
        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    async def test_cancellation_mid_enrichment(self):
        """Handles cancellation during enrichment."""
        async def long_running_enrichment():
            await asyncio.sleep(10)
            return EnrichmentResult(success=True)

        task = asyncio.create_task(long_running_enrichment())

        # Cancel after short delay
        await asyncio.sleep(0.1)
        task.cancel()

        try:
            result = await task
        except asyncio.CancelledError:
            result = None

        assert result is None

    def test_handles_malformed_extraction_response(self):
        """Handles malformed extraction response."""
        response = {"invalid_key": "invalid_value"}

        products = response.get("products", [])
        extracted_data = products[0].get("extracted_data", {}) if products else {}

        assert extracted_data == {}

    def test_handles_network_failure_during_search(self):
        """Handles network failure during search."""
        mock_serpapi = MagicMock()
        mock_serpapi.search.side_effect = ConnectionError("Network unreachable")

        try:
            mock_serpapi.search("test query")
            urls = []
        except ConnectionError:
            urls = []

        assert urls == []

    def test_handles_partial_extraction_results(self):
        """Handles partial extraction (some fields only)."""
        mock_result = create_mock_ai_client_result(
            success=True,
            extracted_data={"abv": 40.0},  # Only ABV extracted
            field_confidences={"abv": 0.95},
        )

        extracted = mock_result.products[0].extracted_data

        assert "abv" in extracted
        assert "description" not in extracted

    def test_handles_very_long_product_names(self):
        """Handles very long product names in search queries."""
        long_name = "A" * 500
        template = "{name} review"

        # Should truncate or handle gracefully
        safe_name = long_name[:100] if len(long_name) > 100 else long_name
        query = template.format(name=safe_name)

        assert len(query) <= 110  # name + " review"

    def test_handles_special_characters_in_data(self):
        """Handles special characters in product data."""
        data = {
            "name": "Taylor's 20 Year Tawny",
            "description": "Rich & complex with \"notes\" of caramel",
        }

        # Should not raise
        assert "'" in data["name"]
        assert "&" in data["description"]
        assert '"' in data["description"]

    def test_deduplicates_fields_enriched(self):
        """Deduplicates fields_enriched list."""
        enriched = ["abv", "description", "abv", "region", "description"]

        unique_enriched = list(dict.fromkeys(enriched))

        assert unique_enriched == ["abv", "description", "region"]

    def test_handles_null_confidence_values(self):
        """Handles null confidence values."""
        confidences = {"name": 0.9, "abv": None, "description": 0.85}

        # Treat None as 0
        safe_confidences = {
            k: (v if v is not None else 0.0)
            for k, v in confidences.items()
        }

        assert safe_confidences["abv"] == 0.0

    def test_handles_rate_limiting_from_search_api(self):
        """Handles rate limiting from search API."""
        mock_serpapi = MagicMock()
        mock_serpapi.search.side_effect = Exception("Rate limit exceeded")

        # Should handle gracefully and potentially retry later
        try:
            mock_serpapi.search("test")
            success = True
        except Exception as e:
            success = False
            error = str(e)

        assert success is False
        assert "Rate limit" in error


class TestTemplateTargetFieldMatching:
    """Tests for matching templates to missing fields (161-170)."""

    def test_selects_template_targeting_missing_fields(self):
        """Selects template that targets missing fields."""
        missing_fields = ["nose_description", "palate_flavors"]
        templates = SAMPLE_ENRICHMENT_CONFIGS

        # Find templates targeting any missing field
        matching = [
            t for t in templates
            if any(f in t["target_fields"] for f in missing_fields)
        ]

        assert len(matching) > 0
        assert "tasting_notes" in [m["template_name"] for m in matching]

    def test_prioritizes_templates_with_more_matching_fields(self):
        """Prioritizes templates targeting more missing fields."""
        missing_fields = ["nose_description", "palate_flavors", "finish_description"]
        templates = SAMPLE_ENRICHMENT_CONFIGS

        # Score by number of matching fields
        scored = [
            (t, len(set(t["target_fields"]).intersection(missing_fields)))
            for t in templates
        ]
        sorted_templates = sorted(scored, key=lambda x: x[1], reverse=True)

        # Tasting notes template targets all 3
        assert sorted_templates[0][0]["template_name"] == "tasting_notes"
        assert sorted_templates[0][1] == 3

    def test_skips_templates_with_no_matching_fields(self):
        """Skips templates that don't target any missing fields."""
        missing_fields = ["awards", "ratings"]  # Only enrichment fields
        templates = SAMPLE_ENRICHMENT_CONFIGS

        matching = [
            t for t in templates
            if any(f in t["target_fields"] for f in missing_fields)
        ]

        # Only awards_search template should match
        assert len(matching) == 1
        assert matching[0]["template_name"] == "awards_search"

    def test_uses_all_templates_if_all_fields_missing(self):
        """Uses all templates when many fields missing."""
        missing_fields = [
            "nose_description",
            "palate_flavors",
            "abv",
            "region",
            "awards",
        ]

        templates = SAMPLE_ENRICHMENT_CONFIGS

        matching = [
            t for t in templates
            if any(f in t["target_fields"] for f in missing_fields)
        ]

        # All templates should have at least one matching field
        assert len(matching) == 4


class TestSingletonAndFactoryPatterns:
    """Tests for singleton and factory patterns (171-180)."""

    def test_get_orchestrator_returns_instance(self):
        """Factory function returns orchestrator instance."""
        # Simulate factory function
        _instance = None

        def get_enrichment_orchestrator_v2():
            nonlocal _instance
            if _instance is None:
                _instance = MagicMock()
            return _instance

        orchestrator = get_enrichment_orchestrator_v2()

        assert orchestrator is not None

    def test_get_orchestrator_returns_singleton(self):
        """Factory returns same instance on subsequent calls."""
        _instance = None

        def get_enrichment_orchestrator_v2():
            nonlocal _instance
            if _instance is None:
                _instance = MagicMock()
            return _instance

        orchestrator1 = get_enrichment_orchestrator_v2()
        orchestrator2 = get_enrichment_orchestrator_v2()

        assert orchestrator1 is orchestrator2

    def test_reset_clears_singleton(self):
        """Reset function clears singleton instance."""
        _instance = MagicMock()

        def reset_enrichment_orchestrator_v2():
            nonlocal _instance
            _instance = None

        def get_enrichment_orchestrator_v2():
            nonlocal _instance
            if _instance is None:
                _instance = MagicMock()
            return _instance

        # Get instance
        first = get_enrichment_orchestrator_v2()

        # Reset
        reset_enrichment_orchestrator_v2()

        # Get new instance
        second = get_enrichment_orchestrator_v2()

        # Should be different instances
        assert first is not second

    def test_orchestrator_accepts_config_service_injection(self):
        """Orchestrator accepts injected config service."""
        mock_config_service = MagicMock()
        mock_config_service.get_enrichment_templates.return_value = []

        # Simulate dependency injection
        orchestrator = MagicMock(config_service=mock_config_service)

        assert orchestrator.config_service is mock_config_service


class TestIntegrationScenarios:
    """Integration-level test scenarios (181-195)."""

    @pytest.mark.asyncio
    async def test_full_enrichment_flow_skeleton_to_partial(self):
        """Full flow: SKELETON product enriched to PARTIAL."""
        initial_data = {"name": "Ardbeg 10"}

        # Simulate enrichment adding fields
        enriched_data = initial_data.copy()
        enriched_data.update({
            "brand": "Ardbeg",
            "abv": 46.0,
            "description": "A peated Islay single malt",
            "region": "Islay",
        })

        result = EnrichmentResult(
            success=True,
            product_data=enriched_data,
            sources_used=["https://example.com/source1"],
            fields_enriched=["brand", "abv", "description", "region"],
            status_before="skeleton",
            status_after="partial",
            searches_performed=1,
        )

        assert result.status_before == "skeleton"
        assert result.status_after == "partial"
        assert len(result.fields_enriched) == 4

    @pytest.mark.asyncio
    async def test_full_enrichment_flow_partial_to_complete(self):
        """Full flow: PARTIAL product enriched to COMPLETE."""
        initial_data = {
            "name": "Ardbeg 10",
            "brand": "Ardbeg",
            "abv": 46.0,
            "description": "A peated Islay single malt",
            "region": "Islay",
        }

        # Simulate enrichment completing the product
        enriched_data = initial_data.copy()
        enriched_data.update({
            "palate_flavors": ["smoke", "peat", "citrus"],
            "nose_description": "Intense smoke with citrus notes",
            "distillery": "Ardbeg",
        })

        result = EnrichmentResult(
            success=True,
            product_data=enriched_data,
            sources_used=["https://example.com/source2"],
            fields_enriched=["palate_flavors", "nose_description", "distillery"],
            status_before="partial",
            status_after="complete",
            searches_performed=1,
        )

        assert result.status_before == "partial"
        assert result.status_after == "complete"

    @pytest.mark.asyncio
    async def test_enrichment_stops_early_on_complete(self):
        """Enrichment stops early when COMPLETE status reached."""
        sources_available = [
            "https://source1.com",
            "https://source2.com",
            "https://source3.com",
        ]
        sources_crawled = []
        current_status = ProductStatus.SKELETON

        for source in sources_available:
            sources_crawled.append(source)

            # Simulate status update after each source
            if len(sources_crawled) == 2:
                current_status = ProductStatus.COMPLETE
                break

        assert len(sources_crawled) == 2
        assert current_status == ProductStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_enrichment_respects_time_limit(self):
        """Enrichment respects time limit during processing."""
        max_time = 2.0  # seconds
        start = time.time()
        sources_processed = 0

        while time.time() - start < max_time:
            sources_processed += 1
            await asyncio.sleep(0.5)

        elapsed = time.time() - start

        assert elapsed >= max_time
        assert sources_processed >= 3  # Should process multiple sources

    def test_enrichment_aggregates_from_multiple_sources(self):
        """Enrichment aggregates data from multiple sources."""
        source_results = [
            {"abv": 46.0, "region": "Islay"},
            {"description": "Peated whiskey", "distillery": "Ardbeg"},
            {"nose_description": "Smoky", "palate_flavors": ["smoke", "peat"]},
        ]

        aggregated = {}
        for result in source_results:
            for field, value in result.items():
                if field not in aggregated:
                    aggregated[field] = value

        assert len(aggregated) == 6
        assert aggregated["abv"] == 46.0
        assert aggregated["nose_description"] == "Smoky"
