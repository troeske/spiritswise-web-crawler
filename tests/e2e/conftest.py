"""
E2E Test Configuration and Fixtures for V2 Architecture.

Provides shared pytest fixtures for real-world E2E testing:
- Database connection (Test Database)
- AI Enhancement Service client
- SerpAPI client
- ScrapingBee client
- Wayback Machine service
- Test run tracking
- Report data collection

IMPORTANT: These tests use REAL external services and do NOT mock anything.
All data created during tests is PRESERVED for manual verification.
"""

import os
import uuid
import logging
from datetime import datetime
from typing import Any, Dict, Generator, List, Optional

import pytest
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)


# =============================================================================
# Skip Decorators for Missing API Keys
# =============================================================================

def requires_ai_service(func):
    """Skip test if AI Enhancement Service is not configured."""
    ai_url = os.getenv("AI_ENHANCEMENT_SERVICE_URL")
    ai_token = os.getenv("AI_ENHANCEMENT_SERVICE_TOKEN")
    return pytest.mark.skipif(
        not ai_url or not ai_token,
        reason="AI_ENHANCEMENT_SERVICE_URL or AI_ENHANCEMENT_SERVICE_TOKEN not configured"
    )(func)


def requires_serpapi(func):
    """Skip test if SerpAPI is not configured."""
    api_key = os.getenv("SERPAPI_API_KEY")
    return pytest.mark.skipif(
        not api_key,
        reason="SERPAPI_API_KEY not configured"
    )(func)


def requires_scrapingbee(func):
    """Skip test if ScrapingBee is not configured."""
    api_key = os.getenv("SCRAPINGBEE_API_KEY")
    return pytest.mark.skipif(
        not api_key,
        reason="SCRAPINGBEE_API_KEY not configured"
    )(func)


# Mark for E2E tests
e2e = pytest.mark.e2e


# =============================================================================
# Test Run Tracking
# =============================================================================

class TestRunTracker:
    """
    Tracks test run metadata and created records.

    Attributes:
        test_run_id: Unique identifier for this test run
        start_time: When the test run started
        end_time: When the test run completed
        created_products: List of product IDs created during tests
        created_sources: List of source IDs created during tests
        created_awards: List of award IDs created during tests
        errors: List of errors encountered
        flow_results: Results from each flow
    """

    def __init__(self):
        self.test_run_id: str = f"e2e-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
        self.start_time: datetime = datetime.now()
        self.end_time: Optional[datetime] = None
        self.created_products: List[uuid.UUID] = []
        self.created_sources: List[uuid.UUID] = []
        self.created_awards: List[uuid.UUID] = []
        self.errors: List[Dict[str, Any]] = []
        self.flow_results: Dict[str, Dict[str, Any]] = {}
        self.api_calls: Dict[str, int] = {
            "openai": 0,
            "serpapi": 0,
            "scrapingbee": 0,
            "wayback": 0,
        }

    def record_product(self, product_id: uuid.UUID) -> None:
        """Record a created product ID."""
        if product_id not in self.created_products:
            self.created_products.append(product_id)

    def record_source(self, source_id: uuid.UUID) -> None:
        """Record a created source ID."""
        if source_id not in self.created_sources:
            self.created_sources.append(source_id)

    def record_award(self, award_id: uuid.UUID) -> None:
        """Record a created award ID."""
        if award_id not in self.created_awards:
            self.created_awards.append(award_id)

    def record_error(self, flow: str, error: str, context: Optional[Dict] = None) -> None:
        """Record an error encountered during testing."""
        self.errors.append({
            "flow": flow,
            "error": error,
            "context": context or {},
            "timestamp": datetime.now().isoformat(),
        })

    def record_api_call(self, service: str, count: int = 1) -> None:
        """Record an API call to an external service."""
        if service in self.api_calls:
            self.api_calls[service] += count

    def record_flow_result(
        self,
        flow_name: str,
        success: bool,
        products_created: int = 0,
        duration_seconds: float = 0.0,
        details: Optional[Dict] = None
    ) -> None:
        """Record the result of a flow execution."""
        self.flow_results[flow_name] = {
            "success": success,
            "products_created": products_created,
            "duration_seconds": duration_seconds,
            "details": details or {},
            "completed_at": datetime.now().isoformat(),
        }

    def finalize(self) -> None:
        """Mark the test run as complete."""
        self.end_time = datetime.now()

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the test run."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        return {
            "test_run_id": self.test_run_id,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": duration,
            "products_created": len(self.created_products),
            "sources_created": len(self.created_sources),
            "awards_created": len(self.created_awards),
            "errors_count": len(self.errors),
            "flows_completed": len(self.flow_results),
            "api_calls": self.api_calls,
        }


# =============================================================================
# Report Data Collector
# =============================================================================

class ReportDataCollector:
    """
    Collects data for generating the final E2E test report.

    Aggregates:
    - Product details
    - Source tracking information
    - Quality assessments
    - Verification results
    """

    def __init__(self):
        self.products: List[Dict[str, Any]] = []
        self.sources: List[Dict[str, Any]] = []
        self.awards: List[Dict[str, Any]] = []
        self.quality_assessments: List[Dict[str, Any]] = []
        self.verification_results: Dict[str, bool] = {}
        self.flow_durations: Dict[str, float] = {}

    def add_product(self, product_data: Dict[str, Any]) -> None:
        """Add product data for reporting."""
        self.products.append(product_data)

    def add_source(self, source_data: Dict[str, Any]) -> None:
        """Add source data for reporting."""
        self.sources.append(source_data)

    def add_award(self, award_data: Dict[str, Any]) -> None:
        """Add award data for reporting."""
        self.awards.append(award_data)

    def add_quality_assessment(self, assessment_data: Dict[str, Any]) -> None:
        """Add quality assessment data for reporting."""
        self.quality_assessments.append(assessment_data)

    def record_verification(self, check_name: str, passed: bool) -> None:
        """Record a verification check result."""
        self.verification_results[check_name] = passed

    def record_flow_duration(self, flow_name: str, duration_seconds: float) -> None:
        """Record the duration of a flow execution."""
        self.flow_durations[flow_name] = duration_seconds

    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for the report."""
        product_types = {}
        status_distribution = {}

        for product in self.products:
            ptype = product.get("product_type", "unknown")
            product_types[ptype] = product_types.get(ptype, 0) + 1

            status = product.get("status", "unknown")
            status_distribution[status] = status_distribution.get(status, 0) + 1

        return {
            "total_products": len(self.products),
            "total_sources": len(self.sources),
            "total_awards": len(self.awards),
            "product_types": product_types,
            "status_distribution": status_distribution,
            "verification_passed": sum(1 for v in self.verification_results.values() if v),
            "verification_failed": sum(1 for v in self.verification_results.values() if not v),
        }


# =============================================================================
# Pytest Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def django_db_setup(django_db_blocker):
    """Configure the test database and run migrations."""
    from django.core.management import call_command

    with django_db_blocker.unblock():
        call_command("migrate", "--run-syncdb", verbosity=0)


@pytest.fixture(scope="session")
def test_run_tracker() -> Generator[TestRunTracker, None, None]:
    """
    Session-scoped fixture for tracking test run metadata.

    Yields the tracker at start and finalizes on completion.
    """
    tracker = TestRunTracker()
    logger.info(f"Starting E2E test run: {tracker.test_run_id}")
    yield tracker
    tracker.finalize()
    logger.info(f"E2E test run completed: {tracker.test_run_id}")
    logger.info(f"Summary: {tracker.get_summary()}")


@pytest.fixture(scope="session")
def report_collector() -> ReportDataCollector:
    """Session-scoped fixture for collecting report data."""
    return ReportDataCollector()


@pytest.fixture(scope="session")
def ai_client():
    """
    Session-scoped fixture for AI Enhancement Service client.

    Uses AI_ENHANCEMENT_SERVICE_URL and AI_ENHANCEMENT_SERVICE_TOKEN from .env.
    Returns None if not configured.
    """
    ai_url = os.getenv("AI_ENHANCEMENT_SERVICE_URL")
    ai_token = os.getenv("AI_ENHANCEMENT_SERVICE_TOKEN")

    if not ai_url or not ai_token:
        logger.warning("AI Enhancement Service not configured, returning None")
        return None

    from crawler.services.ai_client_v2 import AIClientV2

    client = AIClientV2(
        base_url=ai_url,
        api_key=ai_token,
        timeout=120.0,
        max_retries=3,
    )
    logger.info(f"AI Client V2 initialized: {ai_url}")
    return client


@pytest.fixture(scope="session")
def serpapi_client():
    """
    Session-scoped fixture for SerpAPI client.

    Uses SERPAPI_API_KEY from .env.
    Returns None if not configured.
    """
    api_key = os.getenv("SERPAPI_API_KEY")

    if not api_key:
        logger.warning("SerpAPI not configured, returning None")
        return None

    # SerpAPI doesn't have a dedicated client class in the codebase
    # Return a dict with the configuration for use in tests
    return {
        "api_key": api_key,
        "base_url": "https://serpapi.com/search",
    }


@pytest.fixture(scope="session")
def scrapingbee_client():
    """
    Session-scoped fixture for ScrapingBee client.

    Uses SCRAPINGBEE_API_KEY from .env.
    Returns None if not configured.
    """
    api_key = os.getenv("SCRAPINGBEE_API_KEY")

    if not api_key:
        logger.warning("ScrapingBee not configured, returning None")
        return None

    from crawler.services.scrapingbee_client import ScrapingBeeClient

    client = ScrapingBeeClient(api_key=api_key)
    logger.info("ScrapingBee client initialized")
    return client


@pytest.fixture(scope="session")
def wayback_service():
    """
    Session-scoped fixture for Wayback Machine service.

    No API key required - uses public API with rate limiting.
    """
    from crawler.services.wayback_service import WaybackService

    service = WaybackService()
    logger.info("Wayback Machine service initialized")
    return service


@pytest.fixture(scope="session")
def source_tracker():
    """
    Session-scoped fixture for source tracking service.
    """
    from crawler.services.source_tracker import get_source_tracker

    tracker = get_source_tracker()
    logger.info("Source tracker initialized")
    return tracker


@pytest.fixture(scope="session")
def quality_gate():
    """
    Session-scoped fixture for quality gate service.
    """
    from crawler.services.quality_gate_v2 import get_quality_gate_v2

    gate = get_quality_gate_v2()
    logger.info("Quality gate V2 initialized")
    return gate


@pytest.fixture
def db_connection(db):
    """
    Function-scoped fixture for database access.

    Uses Django's test database but does NOT delete data after tests.
    Note: The 'db' fixture is provided by pytest-django.
    """
    return db


@pytest.fixture(scope="session")
def env_config() -> Dict[str, Optional[str]]:
    """
    Session-scoped fixture providing environment configuration.

    Returns a dict with all relevant environment variables.
    """
    return {
        "AI_ENHANCEMENT_SERVICE_URL": os.getenv("AI_ENHANCEMENT_SERVICE_URL"),
        "AI_ENHANCEMENT_SERVICE_TOKEN": os.getenv("AI_ENHANCEMENT_SERVICE_TOKEN"),
        "SERPAPI_API_KEY": os.getenv("SERPAPI_API_KEY"),
        "SCRAPINGBEE_API_KEY": os.getenv("SCRAPINGBEE_API_KEY"),
        "SENTRY_DSN": os.getenv("SENTRY_DSN"),
        "DB_NAME": os.getenv("DB_NAME"),
        "DB_HOST": os.getenv("DB_HOST"),
    }


# =============================================================================
# Helper Fixtures for Test Data
# =============================================================================

@pytest.fixture
def product_factory(db):
    """
    Factory fixture for creating test products.

    Returns a function that creates DiscoveredProduct instances.
    Handles brand as either string (creates DiscoveredBrand) or DiscoveredBrand instance.
    """
    from crawler.models import DiscoveredProduct, DiscoveredBrand, ProductType
    import hashlib

    def _create_product(
        name: str,
        brand: str = "Test Brand",
        product_type: str = ProductType.WHISKEY,
        **kwargs
    ) -> DiscoveredProduct:
        # Handle brand - can be string or DiscoveredBrand instance
        brand_instance = None
        if brand:
            if isinstance(brand, str):
                # Create or get DiscoveredBrand instance
                brand_instance, _ = DiscoveredBrand.objects.get_or_create(name=brand)
            else:
                brand_instance = brand

        # Generate fingerprint if not provided
        if "fingerprint" not in kwargs:
            fp_data = f"{name}:{brand if isinstance(brand, str) else brand.name if brand else ''}"
            kwargs["fingerprint"] = hashlib.sha256(fp_data.encode()).hexdigest()

        # Generate source_url if not provided
        if "source_url" not in kwargs:
            kwargs["source_url"] = f"https://example.com/test-product/{kwargs['fingerprint'][:8]}"

        defaults = {
            "name": name,
            "brand": brand_instance,
            "product_type": product_type,
        }
        defaults.update(kwargs)
        return DiscoveredProduct.objects.create(**defaults)

    return _create_product


@pytest.fixture
def source_factory(db):
    """
    Factory fixture for creating test crawled sources.

    Returns a function that creates CrawledSource instances.
    """
    from crawler.models import CrawledSource

    def _create_source(
        url: str,
        title: str = "Test Source",
        source_type: str = "award_page",
        **kwargs
    ) -> CrawledSource:
        defaults = {
            "url": url,
            "title": title,
            "source_type": source_type,
            "raw_content": kwargs.pop("raw_content", "<html><body>Test</body></html>"),
        }
        defaults.update(kwargs)
        return CrawledSource.objects.create(**defaults)

    return _create_source


@pytest.fixture
def search_term_factory(db):
    """
    Factory fixture for creating test SearchTerms.

    Returns a function that creates SearchTerm instances for Generic Search Discovery testing.

    V2 Spec Reference: Section 7.2 - SearchTerm Model
    """
    from crawler.models import SearchTerm

    def _create_search_term(
        search_query: str = "best whiskey 2026",
        category: str = "best_lists",
        product_type: str = "whiskey",
        max_results: int = 10,
        priority: int = 100,
        is_active: bool = True,
        **kwargs
    ) -> SearchTerm:
        defaults = {
            "search_query": search_query,
            "category": category,
            "product_type": product_type,
            "max_results": max_results,
            "priority": priority,
            "is_active": is_active,
        }
        defaults.update(kwargs)
        return SearchTerm.objects.create(**defaults)

    return _create_search_term


@pytest.fixture
def discovery_job_factory(db):
    """
    Factory fixture for creating test DiscoveryJobs.

    Returns a function that creates DiscoveryJob instances.

    V2 Spec Reference: Section 7.5 - DiscoveryJob Model
    """
    from crawler.models import DiscoveryJob

    def _create_discovery_job(**kwargs) -> DiscoveryJob:
        return DiscoveryJob.objects.create(**kwargs)

    return _create_discovery_job


# =============================================================================
# Parameterization Fixtures for Multi-Product-Type E2E Testing
# =============================================================================

@pytest.fixture
def product_type_config(request, db):
    """
    Fixture that provides ProductTypeTestConfig for parameterized tests.

    Usage:
        @pytest.mark.parametrize("product_type_config", ["whiskey", "port_wine"], indirect=True)
        def test_something(self, product_type_config):
            # product_type_config is a ProductTypeTestConfig instance
            ...
    """
    from tests.e2e.utils.test_products import get_test_config

    product_type = request.param
    return get_test_config(product_type)


@pytest.fixture
def test_product(request, db):
    """
    Fixture that provides a TestProduct for parameterized tests.

    Usage with product type only (returns primary test product):
        @pytest.mark.parametrize("test_product", ["whiskey", "port_wine"], indirect=True)
        def test_something(self, test_product):
            # test_product is the primary TestProduct for each type

    Usage with specific product:
        @pytest.mark.parametrize("test_product",
            [("whiskey", "Frank August..."), ("port_wine", "Taylor's...")],
            indirect=True)
        def test_something(self, test_product):
            # test_product is the specific TestProduct requested
    """
    from tests.e2e.utils.test_products import (
        get_primary_test_product,
        get_test_product_by_name,
    )

    param = request.param
    if isinstance(param, tuple):
        product_type, product_name = param
        return get_test_product_by_name(product_type, product_name)
    else:
        # Param is just product_type, return primary product
        return get_primary_test_product(param)


@pytest.fixture
def setup_product_type_configs(request, db):
    """
    Set up ProductTypeConfig, QualityGateConfig, EnrichmentConfig for a product type.

    This fixture ensures the database has the necessary configuration records
    for the specified product type.

    Usage:
        @pytest.mark.parametrize("setup_product_type_configs", ["whiskey", "port_wine"], indirect=True)
        def test_something(self, setup_product_type_configs):
            # Database is configured for the product type
            ...

    Returns:
        ProductTypeConfig instance from the database
    """
    from crawler.models import ProductTypeConfig, QualityGateConfig, EnrichmentConfig
    from tests.e2e.utils.test_products import get_test_config

    product_type = request.param
    config = get_test_config(product_type)

    # Create or get ProductTypeConfig
    product_type_config, _ = ProductTypeConfig.objects.get_or_create(
        product_type=product_type,
        defaults={
            "display_name": config.display_name,
            "is_active": True,
            "max_sources_per_product": 5,
            "max_serpapi_searches": 3,
            "max_enrichment_time_seconds": 120,
        }
    )

    # Create or get QualityGateConfig
    QualityGateConfig.objects.get_or_create(
        product_type_config=product_type_config,
        defaults={
            "skeleton_required_fields": config.skeleton_fields,
            "partial_required_fields": config.partial_fields,
            "partial_any_of_count": 2,
            "partial_any_of_fields": ["description", "abv", "region", "country"],
            "complete_required_fields": config.complete_fields,
            "complete_any_of_count": 2,
            "complete_any_of_fields": [
                "nose_description",
                "palate_description",
                "finish_description",
                "region",
            ],
        }
    )

    # Create EnrichmentConfigs based on product type
    _create_enrichment_configs_for_type(product_type_config, product_type)

    logger.info(f"Set up configuration for product type: {product_type}")
    return product_type_config


def _create_enrichment_configs_for_type(product_type_config, product_type: str):
    """
    Create enrichment configs for a product type.

    Helper function used by setup_product_type_configs fixture.
    """
    from crawler.models import EnrichmentConfig

    if product_type == "whiskey":
        templates = [
            (
                "tasting_notes",
                "{name} {brand} tasting notes review",
                ["nose_description", "palate_description", "finish_description", "primary_aromas", "palate_flavors"],
                10,
            ),
            (
                "product_details",
                "{name} {brand} bourbon abv alcohol content",
                ["abv", "description", "volume_ml", "age_statement"],
                8,
            ),
        ]
    elif product_type == "port_wine":
        templates = [
            (
                "tasting_notes",
                "{name} {brand} port wine tasting notes review",
                ["nose_description", "palate_description", "finish_description", "primary_aromas", "palate_flavors"],
                10,
            ),
            (
                "producer_info",
                "{name} {brand} port house producer quinta",
                ["producer_house", "quinta", "douro_subregion"],
                8,
            ),
        ]
    else:
        templates = []

    for template_name, search_template, target_fields, priority in templates:
        EnrichmentConfig.objects.get_or_create(
            product_type_config=product_type_config,
            template_name=template_name,
            defaults={
                "search_template": search_template,
                "target_fields": target_fields,
                "priority": priority,
                "is_active": True,
            }
        )


# =============================================================================
# Domain Intelligence Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def redis_client():
    """
    Session-scoped fixture for Redis client.

    Creates a direct Redis connection for E2E tests.
    Uses DB 3 to avoid conflicts with other services.
    Returns None if Redis is not available.
    """
    try:
        import redis

        # Create direct Redis connection (same DB as test cache settings)
        client = redis.Redis(host='localhost', port=6379, db=3)
        # Verify connection
        client.ping()
        logger.info("Redis client connected successfully (direct connection)")
        return client
    except Exception as e:
        logger.warning(f"Could not connect to Redis: {e}")
        return None


@pytest.fixture(scope="session")
def domain_store():
    """
    Create DomainIntelligenceStore connected to Redis.

    Uses Django's cache framework which is already configured for Redis.
    Session-scoped so profiles persist across tests.
    """
    from crawler.fetchers.domain_intelligence import DomainIntelligenceStore

    store = DomainIntelligenceStore()
    logger.info("Created DomainIntelligenceStore with Redis backend")
    return store


@pytest.fixture(scope="function")
def clear_domain_profiles(domain_store):
    """
    Clear domain profiles before a test.

    Use this fixture when you need a clean slate for domain intelligence.
    """
    from django.core.cache import cache

    # Clear all domain profile keys
    # Note: This is a simple approach; production might need pattern-based clearing
    cache.clear()
    logger.info("Cleared all domain profiles from cache")
    yield
    # Optionally clear after test too
    # cache.clear()


@pytest.fixture(scope="session")
def smart_router_with_intelligence(domain_store, redis_client):
    """
    SmartRouter with domain intelligence enabled.

    Session-scoped so it can learn across tests.
    """
    from crawler.fetchers.smart_router import SmartRouter

    router = SmartRouter(
        redis_client=redis_client,
        domain_store=domain_store,
        timeout=30,
    )
    logger.info("Created SmartRouter with domain intelligence")
    yield router


@pytest.fixture(scope="function")
def test_state_manager(request):
    """
    Create TestStateManager for crash recovery.

    Automatically uses the test name as the state identifier.
    """
    from tests.e2e.utils.test_state_manager import TestStateManager

    test_name = request.node.name
    manager = TestStateManager(test_name)
    logger.info(f"Created TestStateManager for test: {test_name}")
    return manager


@pytest.fixture(scope="function")
def results_exporter(request):
    """
    Create ResultsExporter for comprehensive test output.

    Automatically uses the test name for file naming.
    """
    from tests.e2e.utils.results_exporter import ResultsExporter

    test_name = request.node.name
    exporter = ResultsExporter(test_name)
    logger.info(f"Created ResultsExporter for test: {test_name}, output: {exporter.get_filepath()}")
    return exporter


@pytest.fixture(scope="function")
def domain_intelligence_test_context(domain_store, test_state_manager, results_exporter):
    """
    Combined fixture providing all domain intelligence test infrastructure.

    Includes:
    - domain_store: DomainIntelligenceStore
    - state_manager: TestStateManager for crash recovery
    - results_exporter: ResultsExporter for output

    Usage:
        def test_something(self, domain_intelligence_test_context):
            store, state_mgr, exporter = domain_intelligence_test_context
            ...
    """
    return (domain_store, test_state_manager, results_exporter)
