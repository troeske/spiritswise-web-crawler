"""
E2E Test: SearchTerm Configuration and Management

Tests SearchTerm configuration and management per V2 Architecture Spec Sections 7.2, 7.3:
- Create SearchTerms via code (simulating admin)
- Test seasonality filtering
- Test priority ordering
- Test max_results enforcement
- Test search metrics (search_count, products_discovered)

Spec Reference: specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md

IMPORTANT: These tests use the database but do NOT delete data after tests.
"""

import pytest
import logging
from datetime import datetime, date
from django.utils import timezone

from tests.e2e.conftest import e2e

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestSearchTermConfiguration:
    """
    E2E tests for SearchTerm configuration.

    V2 Spec Reference: Section 7.2 - SearchTerm Model
    """

    def test_create_search_term_all_fields(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.2] Create SearchTerm with all fields.
        [STATUS: COMPLETE]
        """
        from crawler.models import SearchTerm

        term = search_term_factory(
            search_query="best bourbon whiskey 2026",
            category="best_lists",
            product_type="whiskey",
            max_results=15,
            priority=50,
            is_active=True,
            seasonal_start_month=11,
            seasonal_end_month=12,
        )

        # Verify all fields
        assert term.search_query == "best bourbon whiskey 2026"
        assert term.category == "best_lists"
        assert term.product_type == "whiskey"
        assert term.max_results == 15
        assert term.priority == 50
        assert term.is_active is True
        assert term.seasonal_start_month == 11
        assert term.seasonal_end_month == 12

        # Verify timestamps
        assert term.created_at is not None
        assert term.updated_at is not None

        # Verify UUID
        assert term.id is not None
        assert len(str(term.id)) == 36  # UUID format

    def test_search_term_default_values(
        self,
        db,
    ):
        """
        [SPEC Section 7.2] SearchTerm default values.
        [STATUS: COMPLETE]
        """
        from crawler.models import SearchTerm

        term = SearchTerm.objects.create(
            search_query="test default values",
            category="best_lists",
            product_type="whiskey",
        )

        # Verify defaults
        assert term.max_results == 10  # Default per spec
        assert term.priority == 100  # Default priority
        assert term.is_active is True  # Default active
        assert term.seasonal_start_month is None
        assert term.seasonal_end_month is None
        assert term.search_count == 0
        assert term.products_discovered == 0
        assert term.last_searched is None

    def test_search_term_bulk_create(
        self,
        db,
    ):
        """
        [SPEC Section 7.3] Bulk create SearchTerms (simulating admin import).
        [STATUS: COMPLETE]
        """
        from crawler.models import SearchTerm

        terms_data = [
            {"search_query": "best whiskey 2026", "category": "best_lists", "product_type": "whiskey", "priority": 100},
            {"search_query": "best bourbon 2026", "category": "best_lists", "product_type": "whiskey", "priority": 100},
            {"search_query": "best scotch 2026", "category": "best_lists", "product_type": "whiskey", "priority": 95},
            {"search_query": "whiskey awards 2026", "category": "awards", "product_type": "whiskey", "priority": 90},
            {"search_query": "best port wine 2026", "category": "best_lists", "product_type": "port_wine", "priority": 100},
        ]

        created_terms = []
        for data in terms_data:
            term = SearchTerm.objects.create(**data)
            created_terms.append(term)

        assert len(created_terms) == 5

        # Verify by category
        whiskey_terms = SearchTerm.objects.filter(product_type="whiskey", is_active=True)
        port_terms = SearchTerm.objects.filter(product_type="port_wine", is_active=True)

        assert whiskey_terms.count() >= 4
        assert port_terms.count() >= 1


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestSearchTermSeasonality:
    """
    E2E tests for SearchTerm seasonality filtering.

    V2 Spec Reference: Section 7.3 - Seasonality Filtering
    """

    def test_year_round_term_always_in_season(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.3] Year-round terms (no seasonal months) always in season.
        [STATUS: COMPLETE]
        """
        term = search_term_factory(
            search_query="year round whiskey",
            seasonal_start_month=None,
            seasonal_end_month=None,
        )

        assert term.is_in_season() is True

    def test_seasonal_term_current_month(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.3] Seasonal term for current month is in season.
        [STATUS: COMPLETE]
        """
        current_month = datetime.now().month

        term = search_term_factory(
            search_query=f"month {current_month} whiskey",
            seasonal_start_month=current_month,
            seasonal_end_month=current_month,
        )

        assert term.is_in_season() is True

    def test_seasonal_term_range(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.3] Seasonal term with date range.
        [STATUS: COMPLETE]
        """
        current_month = datetime.now().month

        # Create term that includes current month in range
        start_month = ((current_month - 2) % 12) + 1  # 2 months before
        end_month = ((current_month + 2) % 12) or 12  # 2 months after

        # Handle edge cases for range that doesn't wrap
        if start_month < end_month:
            term = search_term_factory(
                search_query="range term",
                seasonal_start_month=start_month,
                seasonal_end_month=end_month,
            )
            assert term.is_in_season() is True

    def test_seasonal_term_wrapping_range(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.3] Seasonal term with wrapping range (e.g., Nov-Feb).
        [STATUS: COMPLETE]
        """
        # Holiday season term (November to February)
        term = search_term_factory(
            search_query="holiday whiskey gifts",
            seasonal_start_month=11,
            seasonal_end_month=2,
        )

        current_month = datetime.now().month
        expected_in_season = current_month >= 11 or current_month <= 2
        assert term.is_in_season() is expected_in_season


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestSearchTermPriority:
    """
    E2E tests for SearchTerm priority ordering.

    V2 Spec Reference: Section 7.3 - Priority Ordering
    """

    def test_priority_ordering_ascending(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.3] Lower priority number = higher priority.
        [STATUS: COMPLETE]
        """
        # Create terms with different priorities
        search_term_factory(search_query="priority 200", priority=200)
        search_term_factory(search_query="priority 50", priority=50)
        search_term_factory(search_query="priority 100", priority=100)
        search_term_factory(search_query="priority 1", priority=1)

        from crawler.models import SearchTerm
        ordered = SearchTerm.objects.filter(is_active=True).order_by("priority")

        priorities = [t.priority for t in ordered]
        assert priorities == sorted(priorities)

        # First term should have lowest priority number (highest importance)
        first_term = ordered.first()
        assert first_term.priority <= 50

    def test_priority_secondary_sort_by_products_discovered(
        self,
        db,
    ):
        """
        [SPEC Section 7.3] Secondary sort by products_discovered (descending).
        [STATUS: COMPLETE]
        """
        from crawler.models import SearchTerm

        # Create terms with same priority but different discovery counts
        term1 = SearchTerm.objects.create(
            search_query="term1 same priority",
            category="best_lists",
            product_type="whiskey",
            priority=100,
        )
        term1.products_discovered = 10
        term1.save()

        term2 = SearchTerm.objects.create(
            search_query="term2 same priority",
            category="best_lists",
            product_type="whiskey",
            priority=100,
        )
        term2.products_discovered = 50
        term2.save()

        term3 = SearchTerm.objects.create(
            search_query="term3 same priority",
            category="best_lists",
            product_type="whiskey",
            priority=100,
        )
        term3.products_discovered = 25
        term3.save()

        # Query with Meta ordering (priority, -products_discovered)
        ordered = SearchTerm.objects.filter(
            search_query__contains="same priority"
        ).order_by("priority", "-products_discovered")

        counts = [t.products_discovered for t in ordered]
        # Should be sorted by products_discovered descending within same priority
        assert counts == sorted(counts, reverse=True)


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestSearchTermMetrics:
    """
    E2E tests for SearchTerm metrics tracking.

    V2 Spec Reference: Section 7.2 - SearchTerm Model (metrics fields)
    """

    def test_search_count_increment(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.2] search_count tracks number of searches.
        [STATUS: COMPLETE]
        """
        term = search_term_factory()
        assert term.search_count == 0

        # Simulate searches
        for i in range(5):
            term.search_count += 1
            term.save()

        term.refresh_from_db()
        assert term.search_count == 5

    def test_products_discovered_increment(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.2] products_discovered tracks discovery count.
        [STATUS: COMPLETE]
        """
        term = search_term_factory()
        assert term.products_discovered == 0

        # Simulate product discovery
        term.products_discovered += 15
        term.save()

        term.refresh_from_db()
        assert term.products_discovered == 15

    def test_last_searched_timestamp(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.2] last_searched tracks when term was used.
        [STATUS: COMPLETE]
        """
        term = search_term_factory()
        assert term.last_searched is None

        # Simulate search
        now = timezone.now()
        term.last_searched = now
        term.search_count += 1
        term.save()

        term.refresh_from_db()
        assert term.last_searched is not None
        assert abs((term.last_searched - now).total_seconds()) < 1

    def test_metrics_aggregation(
        self,
        db,
        search_term_factory,
    ):
        """
        [SPEC Section 7.2] Aggregate metrics across terms.
        [STATUS: COMPLETE]
        """
        from django.db.models import Sum
        from crawler.models import SearchTerm

        # Create terms with metrics
        for i in range(3):
            term = search_term_factory(
                search_query=f"metrics test {i}",
            )
            term.search_count = (i + 1) * 10
            term.products_discovered = (i + 1) * 5
            term.save()

        # Aggregate
        totals = SearchTerm.objects.filter(
            search_query__startswith="metrics test"
        ).aggregate(
            total_searches=Sum("search_count"),
            total_products=Sum("products_discovered"),
        )

        assert totals["total_searches"] == 60  # 10 + 20 + 30
        assert totals["total_products"] == 30  # 5 + 10 + 15


@pytest.mark.e2e
@pytest.mark.django_db(transaction=True)
class TestSearchTermValidation:
    """
    E2E tests for SearchTerm validation.

    V2 Spec Reference: Section 7.2 - SearchTerm Model (validators)
    """

    def test_max_results_min_validation(
        self,
        db,
    ):
        """
        [SPEC Section 7.2] max_results minimum is 1.
        [STATUS: COMPLETE]
        """
        from django.core.exceptions import ValidationError
        from crawler.models import SearchTerm

        term = SearchTerm(
            search_query="invalid min",
            category="best_lists",
            product_type="whiskey",
            max_results=0,
        )

        with pytest.raises(ValidationError):
            term.full_clean()

    def test_max_results_max_validation(
        self,
        db,
    ):
        """
        [SPEC Section 7.2] max_results maximum is 20.
        [STATUS: COMPLETE]
        """
        from django.core.exceptions import ValidationError
        from crawler.models import SearchTerm

        term = SearchTerm(
            search_query="invalid max",
            category="best_lists",
            product_type="whiskey",
            max_results=21,
        )

        with pytest.raises(ValidationError):
            term.full_clean()

    def test_seasonal_month_validation(
        self,
        db,
    ):
        """
        [SPEC Section 7.2] Seasonal months must be 1-12.
        [STATUS: COMPLETE]
        """
        from django.core.exceptions import ValidationError
        from crawler.models import SearchTerm

        # Invalid start month
        term = SearchTerm(
            search_query="invalid month",
            category="best_lists",
            product_type="whiskey",
            seasonal_start_month=13,
        )

        with pytest.raises(ValidationError):
            term.full_clean()

    def test_category_choices_validation(
        self,
        db,
    ):
        """
        [SPEC Section 7.2] Category must be valid choice.
        [STATUS: COMPLETE]
        """
        from django.core.exceptions import ValidationError
        from crawler.models import SearchTerm

        term = SearchTerm(
            search_query="invalid category",
            category="invalid_category",
            product_type="whiskey",
        )

        with pytest.raises(ValidationError):
            term.full_clean()

    def test_product_type_choices_validation(
        self,
        db,
    ):
        """
        [SPEC Section 7.2] Product type must be valid choice.
        [STATUS: COMPLETE]
        """
        from django.core.exceptions import ValidationError
        from crawler.models import SearchTerm

        term = SearchTerm(
            search_query="invalid product type",
            category="best_lists",
            product_type="invalid_type",
        )

        with pytest.raises(ValidationError):
            term.full_clean()
