# Section 13: REST API Endpoints

> **Source**: Lines 3047-3951 from `FLOW_COMPARISON_ANALYSIS.md`

---

## 13. REST API Endpoints

The crawler exposes REST API endpoints for on-demand extraction and crawl triggering.

### 13.1 API Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           REST API ENDPOINTS                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  EXTRACTION ENDPOINTS (On-demand product extraction)                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  POST /api/v1/extract/url/                                            │   │
│  │  Extract product(s) from a single URL (list or detail page)           │   │
│  │                                                                        │   │
│  │  POST /api/v1/extract/urls/                                           │   │
│  │  Batch extract from multiple URLs                                      │   │
│  │                                                                        │   │
│  │  POST /api/v1/extract/search/                                         │   │
│  │  Search + extract (SerpAPI → SmartCrawler)                            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  CRAWL TRIGGER ENDPOINTS (Award site crawls)                                │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  POST /api/v1/crawl/awards/                                           │   │
│  │  Trigger unscheduled award site crawl                                  │   │
│  │                                                                        │   │
│  │  GET  /api/v1/crawl/awards/status/{job_id}/                           │   │
│  │  Check crawl job status                                                │   │
│  │                                                                        │   │
│  │  GET  /api/v1/crawl/awards/sources/                                   │   │
│  │  List available award sources with health status                       │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  HEALTH & MONITORING                                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  GET  /api/health/                     (existing)                     │   │
│  │  GET  /api/v1/sources/health/          Source-level health            │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 13.2 Extraction Endpoints

#### POST /api/v1/extract/url/

Extract product(s) from a single URL. Automatically detects if URL is a list page or single product page.

**Request:**
```json
{
  "url": "https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/",
  "product_type": "whiskey",           // Optional: "whiskey", "port_wine", "auto"
  "save_to_db": true,                  // Optional: Save to DiscoveredProduct (default: true)
  "enrich": true                       // Optional: Run multi-source enrichment (default: false)
}
```

**Response (Single Product):**
```json
{
  "success": true,
  "page_type": "single_product",
  "products": [
    {
      "id": 12345,                     // DiscoveredProduct.id if saved
      "name": "Ardbeg 10 Year Old",
      "brand": "Ardbeg",
      "product_type": "whiskey",
      "abv": 46.0,
      "status": "partial",
      "completeness_score": 45,
      "source_url": "https://www.masterofmalt.com/...",
      "palate_description": "Smoky with citrus notes...",
      "nose_description": "Intense peat smoke...",
      "has_tasting_profile": true
    }
  ],
  "extraction_time_ms": 2340
}
```

**Response (List Page):**
```json
{
  "success": true,
  "page_type": "list_page",
  "products_found": 12,
  "products_extracted": 10,
  "products_failed": 2,
  "products": [
    { "id": 12345, "name": "Product 1", "status": "partial", ... },
    { "id": 12346, "name": "Product 2", "status": "complete", ... }
  ],
  "failed_products": [
    { "name": "Product X", "error": "Extraction timeout" }
  ],
  "extraction_time_ms": 15420
}
```

#### POST /api/v1/extract/urls/

Batch extract from multiple URLs.

**Request:**
```json
{
  "urls": [
    "https://www.masterofmalt.com/whiskies/ardbeg/ardbeg-10-year-old-whisky/",
    "https://www.thewhiskyexchange.com/p/12345/lagavulin-16-year-old",
    "https://www.wine.com/product/taylors-10-year-tawny-port/123456"
  ],
  "product_type": "auto",              // Auto-detect per URL
  "save_to_db": true,
  "parallel": true                     // Process URLs in parallel (default: true)
}
```

**Response:**
```json
{
  "success": true,
  "total_urls": 3,
  "successful": 3,
  "failed": 0,
  "products_extracted": 3,
  "results": [
    { "url": "https://...", "success": true, "product_id": 12345 },
    { "url": "https://...", "success": true, "product_id": 12346 },
    { "url": "https://...", "success": true, "product_id": 12347 }
  ],
  "extraction_time_ms": 8540
}
```

#### POST /api/v1/extract/search/

Search for a product and extract from best results.

**Request:**
```json
{
  "query": "Ardbeg Uigeadail whisky",
  "product_type": "whiskey",
  "num_results": 5,                    // Number of search results to try
  "save_to_db": true,
  "prefer_official": true              // Prefer official brand sites (default: true)
}
```

**Response:**
```json
{
  "success": true,
  "query": "Ardbeg Uigeadail whisky",
  "search_results_found": 10,
  "urls_tried": 3,
  "product": {
    "id": 12345,
    "name": "Ardbeg Uigeadail",
    "source_url": "https://www.ardbeg.com/en-US/whisky/ultimate-range/uigeadail",
    "source_type": "official_brand",
    "status": "complete",
    "completeness_score": 75
  },
  "extraction_time_ms": 4520
}
```

### 13.3 Award Crawl Trigger Endpoints

#### POST /api/v1/crawl/awards/

Trigger an unscheduled award site crawl.

**Request:**
```json
{
  "source": "iwsc",                    // "iwsc", "dwwa", "sfwsc", "wwa"
  "year": 2025,                        // Optional: defaults to current year
  "product_types": ["port_wine"],      // Optional: filter by product type
  "run_health_check": true,            // Optional: run health check first (default: true)
  "async": true                        // Optional: return immediately with job_id (default: true)
}
```

**Response (async=true):**
```json
{
  "success": true,
  "job_id": "award-crawl-iwsc-2025-abc123",
  "source": "iwsc",
  "year": 2025,
  "status": "queued",
  "health_check": {
    "passed": true,
    "selectors_healthy": 3,
    "selectors_total": 3
  },
  "estimated_products": 150,
  "status_url": "/api/v1/crawl/awards/status/award-crawl-iwsc-2025-abc123/"
}
```

**Response (async=false):**
```json
{
  "success": true,
  "job_id": "award-crawl-iwsc-2025-abc123",
  "source": "iwsc",
  "year": 2025,
  "status": "completed",
  "products_found": 145,
  "products_saved": 142,
  "products_failed": 3,
  "new_products": 89,
  "updated_products": 53,
  "duration_seconds": 342,
  "errors": [
    { "url": "https://...", "error": "Extraction failed" }
  ]
}
```

#### GET /api/v1/crawl/awards/status/{job_id}/

Check status of a crawl job.

**Response:**
```json
{
  "job_id": "award-crawl-iwsc-2025-abc123",
  "source": "iwsc",
  "year": 2025,
  "status": "running",                 // "queued", "running", "completed", "failed"
  "progress": {
    "pages_processed": 5,
    "pages_total": 12,
    "products_found": 85,
    "products_saved": 82,
    "current_page": "https://www.iwsc.net/results/2025?page=6"
  },
  "started_at": "2026-01-05T14:30:00Z",
  "elapsed_seconds": 145
}
```

#### GET /api/v1/crawl/awards/sources/

List available award sources with health status.

**Response:**
```json
{
  "sources": [
    {
      "id": "iwsc",
      "name": "International Wine & Spirit Competition",
      "url": "https://www.iwsc.net",
      "product_types": ["whiskey", "port_wine", "gin", "vodka"],
      "requires_playwright": false,
      "health": {
        "status": "healthy",
        "last_check": "2026-01-05T06:00:00Z",
        "selectors_healthy": 3,
        "last_crawl": "2026-01-04T06:15:00Z",
        "last_crawl_products": 245
      },
      "schedule": {
        "enabled": true,
        "cron": "0 6 * * 1",
        "next_run": "2026-01-06T06:00:00Z"
      }
    },
    {
      "id": "dwwa",
      "name": "Decanter World Wine Awards",
      "url": "https://awards.decanter.com",
      "product_types": ["port_wine", "wine"],
      "requires_playwright": true,
      "health": {
        "status": "healthy",
        "last_check": "2026-01-05T06:00:00Z",
        "selectors_healthy": 3,
        "last_crawl": "2025-12-30T06:15:00Z",
        "last_crawl_products": 89
      },
      "schedule": {
        "enabled": true,
        "cron": "0 6 * * 1",
        "next_run": "2026-01-06T06:00:00Z"
      }
    }
  ]
}
```

### 13.4 Source Health Endpoint

#### GET /api/v1/sources/health/

Get health status for all sources (award sites + retailers).

**Response:**
```json
{
  "overall_status": "healthy",
  "sources": {
    "award_sites": [
      {
        "id": "iwsc",
        "status": "healthy",
        "last_health_check": "2026-01-05T06:00:00Z",
        "checks": {
          "selector_health": "passed",
          "fingerprint_match": true,
          "last_yield": 245
        }
      }
    ],
    "retailers": [
      {
        "domain": "masterofmalt.com",
        "status": "healthy",
        "success_rate_24h": 0.94,
        "avg_extraction_time_ms": 2150
      }
    ]
  }
}
```

### 13.5 Authentication & Rate Limiting

```python
# API Authentication (add to settings)
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.TokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',  # For admin UI
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '100/hour',           # General rate limit
        'extraction': '50/hour',       # Extraction endpoints
        'crawl_trigger': '10/hour',    # Crawl triggers
    },
}
```

### 13.6 Implementation: Views

```python
# crawler/api/views.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import UserRateThrottle

from crawler.services.smart_crawler import SmartCrawler
from crawler.services.discovery_orchestrator import DiscoveryOrchestrator
from crawler.discovery.collectors import get_collector
from crawler.tasks import trigger_award_crawl


class ExtractionThrottle(UserRateThrottle):
    rate = '50/hour'


class CrawlTriggerThrottle(UserRateThrottle):
    rate = '10/hour'


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExtractionThrottle])
def extract_from_url(request):
    """
    Extract product(s) from a single URL.
    Automatically detects list page vs single product page.
    """
    url = request.data.get('url')
    if not url:
        return Response(
            {'error': 'url is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product_type = request.data.get('product_type', 'auto')
    save_to_db = request.data.get('save_to_db', True)
    enrich = request.data.get('enrich', False)

    try:
        crawler = SmartCrawler()
        start_time = time.time()

        # Detect page type and extract
        result = crawler.extract_from_url(
            url=url,
            product_type=product_type,
            save_to_db=save_to_db,
            enrich=enrich,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return Response({
            'success': True,
            'page_type': result.page_type,
            'products': result.products,
            'extraction_time_ms': elapsed_ms,
        })

    except Exception as e:
        logger.exception(f"Extraction failed for {url}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExtractionThrottle])
def extract_from_urls(request):
    """Batch extract from multiple URLs."""
    urls = request.data.get('urls', [])
    if not urls:
        return Response(
            {'error': 'urls is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(urls) > 50:
        return Response(
            {'error': 'Maximum 50 URLs per request'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product_type = request.data.get('product_type', 'auto')
    save_to_db = request.data.get('save_to_db', True)
    parallel = request.data.get('parallel', True)

    try:
        crawler = SmartCrawler()
        start_time = time.time()

        if parallel:
            # Use asyncio for parallel extraction
            results = asyncio.run(
                crawler.extract_from_urls_parallel(urls, product_type, save_to_db)
            )
        else:
            results = crawler.extract_from_urls_sequential(urls, product_type, save_to_db)

        elapsed_ms = int((time.time() - start_time) * 1000)

        successful = sum(1 for r in results if r['success'])
        products_extracted = sum(len(r.get('products', [])) for r in results if r['success'])

        return Response({
            'success': True,
            'total_urls': len(urls),
            'successful': successful,
            'failed': len(urls) - successful,
            'products_extracted': products_extracted,
            'results': results,
            'extraction_time_ms': elapsed_ms,
        })

    except Exception as e:
        logger.exception("Batch extraction failed")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExtractionThrottle])
def extract_from_search(request):
    """Search for a product and extract from best results."""
    query = request.data.get('query')
    if not query:
        return Response(
            {'error': 'query is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product_type = request.data.get('product_type', 'auto')
    num_results = min(request.data.get('num_results', 5), 10)
    save_to_db = request.data.get('save_to_db', True)
    prefer_official = request.data.get('prefer_official', True)

    try:
        crawler = SmartCrawler()
        start_time = time.time()

        result = crawler.extract_product(
            search_term=query,
            product_type=product_type,
            save_to_db=save_to_db,
            prefer_official=prefer_official,
            max_search_results=num_results,
        )

        elapsed_ms = int((time.time() - start_time) * 1000)

        return Response({
            'success': result.success,
            'query': query,
            'search_results_found': result.search_results_count,
            'urls_tried': len(result.urls_tried),
            'product': result.product if result.success else None,
            'error': result.error if not result.success else None,
            'extraction_time_ms': elapsed_ms,
        })

    except Exception as e:
        logger.exception(f"Search extraction failed for: {query}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([CrawlTriggerThrottle])
def trigger_award_crawl_view(request):
    """Trigger an unscheduled award site crawl."""
    source = request.data.get('source')
    if not source:
        return Response(
            {'error': 'source is required (iwsc, dwwa, sfwsc, wwa)'},
            status=status.HTTP_400_BAD_REQUEST
        )

    valid_sources = ['iwsc', 'dwwa', 'sfwsc', 'wwa']
    if source not in valid_sources:
        return Response(
            {'error': f'Invalid source. Must be one of: {valid_sources}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    year = request.data.get('year', datetime.now().year)
    product_types = request.data.get('product_types')
    run_health_check = request.data.get('run_health_check', True)
    is_async = request.data.get('async', True)

    try:
        # Run health check first if requested
        health_result = None
        if run_health_check:
            from crawler.discovery.health import SelectorHealthChecker
            checker = SelectorHealthChecker()
            health_report = asyncio.run(checker.check_source(source, year))

            if not health_report.is_healthy:
                return Response({
                    'success': False,
                    'error': 'Health check failed - site structure may have changed',
                    'health_check': {
                        'passed': False,
                        'failed_selectors': health_report.failed_selectors,
                    }
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

            health_result = {
                'passed': True,
                'selectors_healthy': health_report.selectors_healthy,
                'selectors_total': health_report.selectors_tested,
            }

        # Generate job ID
        job_id = f"award-crawl-{source}-{year}-{uuid.uuid4().hex[:8]}"

        if is_async:
            # Queue the crawl task
            trigger_award_crawl.delay(
                job_id=job_id,
                source=source,
                year=year,
                product_types=product_types,
            )

            return Response({
                'success': True,
                'job_id': job_id,
                'source': source,
                'year': year,
                'status': 'queued',
                'health_check': health_result,
                'status_url': f'/api/v1/crawl/awards/status/{job_id}/',
            })
        else:
            # Run synchronously (blocking)
            result = run_award_crawl_sync(
                job_id=job_id,
                source=source,
                year=year,
                product_types=product_types,
            )

            return Response({
                'success': True,
                'job_id': job_id,
                **result,
            })

    except Exception as e:
        logger.exception(f"Failed to trigger award crawl for {source}")
        return Response(
            {'success': False, 'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_crawl_status(request, job_id):
    """Get status of a crawl job."""
    try:
        from crawler.models import CrawlJob
        job = CrawlJob.objects.get(job_id=job_id)

        return Response({
            'job_id': job.job_id,
            'source': job.source,
            'year': job.year,
            'status': job.status,
            'progress': job.progress,
            'started_at': job.started_at.isoformat() if job.started_at else None,
            'completed_at': job.completed_at.isoformat() if job.completed_at else None,
            'elapsed_seconds': job.elapsed_seconds,
            'error': job.error,
        })

    except CrawlJob.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_award_sources(request):
    """List available award sources with health status."""
    from crawler.discovery.health import SelectorHealthChecker
    from crawler.models import SourceHealthCheck, CrawlSchedule

    sources = []
    source_configs = {
        'iwsc': {
            'name': 'International Wine & Spirit Competition',
            'url': 'https://www.iwsc.net',
            'product_types': ['whiskey', 'port_wine', 'gin', 'vodka'],
            'requires_playwright': False,
        },
        'dwwa': {
            'name': 'Decanter World Wine Awards',
            'url': 'https://awards.decanter.com',
            'product_types': ['port_wine', 'wine'],
            'requires_playwright': True,
        },
        'sfwsc': {
            'name': 'San Francisco World Spirits Competition',
            'url': 'https://sfwsc.com',
            'product_types': ['whiskey', 'gin', 'vodka', 'rum', 'tequila'],
            'requires_playwright': False,
        },
        'wwa': {
            'name': 'World Whiskies Awards',
            'url': 'https://www.worldwhiskiesawards.com',
            'product_types': ['whiskey'],
            'requires_playwright': False,
        },
    }

    for source_id, config in source_configs.items():
        # Get latest health check
        health_check = SourceHealthCheck.objects.filter(
            source=source_id
        ).order_by('-checked_at').first()

        # Get schedule
        schedule = CrawlSchedule.objects.filter(
            source_id=source_id
        ).first()

        sources.append({
            'id': source_id,
            **config,
            'health': {
                'status': 'healthy' if health_check and health_check.is_healthy else 'unknown',
                'last_check': health_check.checked_at.isoformat() if health_check else None,
                'selectors_healthy': health_check.details.get('selectors_healthy') if health_check else None,
            } if health_check else {'status': 'unknown'},
            'schedule': {
                'enabled': schedule.enabled if schedule else False,
                'cron': schedule.cron_expression if schedule else None,
                'next_run': schedule.next_run.isoformat() if schedule and schedule.next_run else None,
            } if schedule else {'enabled': False},
        })

    return Response({'sources': sources})
```

### 13.7 URL Configuration

```python
# crawler/api/urls.py

from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Extraction endpoints
    path('extract/url/', views.extract_from_url, name='extract-url'),
    path('extract/urls/', views.extract_from_urls, name='extract-urls'),
    path('extract/search/', views.extract_from_search, name='extract-search'),

    # Award crawl endpoints
    path('crawl/awards/', views.trigger_award_crawl_view, name='trigger-award-crawl'),
    path('crawl/awards/status/<str:job_id>/', views.get_crawl_status, name='crawl-status'),
    path('crawl/awards/sources/', views.list_award_sources, name='award-sources'),

    # Health endpoints
    path('sources/health/', views.sources_health, name='sources-health'),
]


# config/urls.py - update to include API
urlpatterns = [
    # ... existing patterns ...
    path("api/v1/", include("crawler.api.urls")),
]
```

### 13.8 Celery Task for Async Crawl

```python
# crawler/tasks/award_crawl.py

from celery import shared_task
from crawler.models import CrawlJob
from crawler.discovery.collectors import get_collector
from crawler.discovery.extractors import AIExtractor


@shared_task(bind=True)
def trigger_award_crawl(self, job_id: str, source: str, year: int, product_types: list = None):
    """
    Celery task to run award site crawl asynchronously.
    Updates CrawlJob model with progress.
    """
    from django.utils import timezone

    # Create or update job record
    job, _ = CrawlJob.objects.update_or_create(
        job_id=job_id,
        defaults={
            'source': source,
            'year': year,
            'status': 'running',
            'started_at': timezone.now(),
            'celery_task_id': self.request.id,
        }
    )

    try:
        collector = get_collector(source)
        extractor = AIExtractor()

        # Collect URLs from listing pages
        detail_urls = collector.collect(year=year, product_types=product_types)

        job.progress = {
            'pages_processed': 0,
            'pages_total': len(detail_urls),
            'products_found': len(detail_urls),
            'products_saved': 0,
        }
        job.save()

        # Extract from each detail URL
        saved_count = 0
        errors = []

        for i, url_info in enumerate(detail_urls):
            try:
                product_data = extractor.extract(
                    url=url_info.detail_url,
                    context={
                        'source': source,
                        'year': year,
                        'medal_hint': url_info.medal_hint,
                        'score_hint': url_info.score_hint,
                    }
                )

                if product_data:
                    save_discovered_product(product_data, source=source)
                    saved_count += 1

            except Exception as e:
                errors.append({'url': url_info.detail_url, 'error': str(e)})

            # Update progress
            job.progress['pages_processed'] = i + 1
            job.progress['products_saved'] = saved_count
            job.save()

        # Mark complete
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.progress['errors'] = errors[:10]  # Keep first 10 errors
        job.save()

    except Exception as e:
        job.status = 'failed'
        job.error = str(e)
        job.completed_at = timezone.now()
        job.save()
        raise
```

### 13.9 CrawlJob Model

```python
# Add to crawler/models.py

class CrawlJob(models.Model):
    """Track async crawl jobs triggered via API."""

    job_id = models.CharField(max_length=100, unique=True, db_index=True)
    source = models.CharField(max_length=50)
    year = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=[
            ('queued', 'Queued'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='queued',
    )
    progress = models.JSONField(default=dict)
    error = models.TextField(null=True, blank=True)
    celery_task_id = models.CharField(max_length=100, null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'crawl_job'
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['source', 'year']),
        ]

    @property
    def elapsed_seconds(self) -> int:
        if not self.started_at:
            return 0
        end = self.completed_at or timezone.now()
        return int((end - self.started_at).total_seconds())
```

---

## Summary

This spec defines a unified product pipeline that:

1. **Requires tasting profile for COMPLETE/VERIFIED** - Products CANNOT be marked complete without palate data
2. **Verifies from multiple sources** - Target 2-3 sources per product, track `source_count` and `verified_fields`
3. **Uses proper database columns** - No JSON blobs for searchable data, individual columns for all tasting fields
4. **Maintains model split** - DiscoveredProduct + WhiskeyDetails + PortWineDetails
5. **Uses completeness scoring** - Tasting = 40%, with palate being mandatory for COMPLETE status
6. **URL Collector → AI Extraction for awards** - Specialized collectors find detail page URLs, unified AI extracts all data
7. **DWWA support for Port wines** - Playwright-based collector for JavaScript-rendered DWWA site, includes non-Portuguese port-style wines
8. **Structural change detection** - Multi-layer detection (selector health, yield monitoring, fingerprinting, known product verification) with automated alerts and crawl abort on failure
9. **REST API for extraction & crawl triggers** - On-demand extraction from URLs/search, async award crawl triggering with job status tracking

---

*Document created: 2026-01-05*
*Last updated: 2026-01-05*
*Version: 2.4 - Added REST API endpoints for extraction and award crawl triggers (Section 13)*
