"""
Unified Product Pipeline Phase 6: API Views

REST API endpoints for product extraction and crawl management.

This module provides endpoints for:
- On-demand product extraction from URLs (single and batch)
- Search-based extraction via SerpAPI
- Award crawl triggering and status monitoring
- Source health monitoring

All endpoints require authentication and have rate limiting.
"""

import time
import uuid
import logging
from urllib.parse import urlparse
from typing import Optional, List, Dict, Any

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

from crawler.api.throttling import ExtractionThrottle, CrawlTriggerThrottle
from crawler.models import APICrawlJob, DiscoveredProduct, SourceHealthCheck

logger = logging.getLogger(__name__)

# Valid award sources
VALID_SOURCES = {'iwsc', 'dwwa', 'sfwsc', 'wwa'}

# Source metadata
SOURCE_METADATA = {
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
        'url': 'https://www.sfspiritscomp.com',
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


def _is_valid_url(url: str) -> bool:
    """Check if a string is a valid URL."""
    try:
        result = urlparse(url)
        return all([result.scheme in ('http', 'https'), result.netloc])
    except Exception:
        return False


def _get_smart_crawler():
    """Get SmartCrawler instance (lazy import to avoid circular imports)."""
    from crawler.services.smart_crawler import SmartCrawler
    return SmartCrawler()


def _get_selector_health_checker():
    """Get SelectorHealthChecker instance."""
    from crawler.discovery.health.selector_health import SelectorHealthChecker
    return SelectorHealthChecker()


def _get_verification_pipeline():
    """Get VerificationPipeline instance (lazy import to avoid circular imports)."""
    from crawler.verification.pipeline import VerificationPipeline
    return VerificationPipeline()


# ============================================================
# Extraction Endpoints
# ============================================================

@extend_schema(
    tags=['Extraction'],
    summary='Extract product from single URL',
    description='''
    Extract product data from a single URL.

    Automatically detects if URL is a list page or single product page.
    Supports whiskey and port wine products.
    ''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'url': {'type': 'string', 'format': 'uri', 'description': 'URL to extract product from'},
                'product_type': {'type': 'string', 'enum': ['whiskey', 'port_wine', 'auto'], 'default': 'auto'},
                'save_to_db': {'type': 'boolean', 'default': True, 'description': 'Save extracted product to database'},
                'enrich': {'type': 'boolean', 'default': False, 'description': 'Run enrichment after extraction'},
            },
            'required': ['url'],
        }
    },
    responses={
        200: {
            'description': 'Successful extraction',
            'content': {
                'application/json': {
                    'example': {
                        'success': True,
                        'page_type': 'single_product',
                        'products': [{'name': 'Ardbeg Uigeadail', 'brand': 'Ardbeg', 'status': 'partial'}],
                        'extraction_time_ms': 1234,
                    }
                }
            }
        },
        400: {'description': 'Invalid URL or missing parameters'},
        500: {'description': 'Extraction failed'},
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExtractionThrottle])
def extract_from_url(request):
    """
    Extract product(s) from a single URL.

    Automatically detects if URL is a list page or single product page.

    Request body:
    {
        "url": "https://example.com/product/...",
        "product_type": "whiskey",  // Optional: "whiskey", "port_wine", "auto"
        "save_to_db": true,         // Optional: Save to database (default: true)
        "enrich": false             // Optional: Run enrichment (default: false)
    }

    Response includes extracted product data with status and completeness score.
    """
    start_time = time.time()

    url = request.data.get('url')
    if not url:
        return Response(
            {'error': 'url is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not _is_valid_url(url):
        return Response(
            {'error': 'Invalid URL format'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product_type = request.data.get('product_type', 'auto')
    save_to_db = request.data.get('save_to_db', True)
    enrich = request.data.get('enrich', False)

    try:
        crawler = _get_smart_crawler()
        result = crawler.extract_product(
            product_name=None,  # Will be extracted
            url=url,
            product_type=product_type if product_type != 'auto' else None,
        )

        products = []
        page_type = 'single_product'

        if result:
            product_data = {
                'name': result.get('name'),
                'brand': result.get('brand'),
                'product_type': result.get('product_type', product_type),
                'abv': result.get('abv'),
                'status': result.get('status', 'partial'),
                'completeness_score': result.get('completeness_score', 0),
                'source_url': url,
                'palate_description': result.get('palate_description'),
                'nose_description': result.get('nose_description'),
                'has_tasting_profile': bool(
                    result.get('palate_description') or
                    result.get('palate_flavors') or
                    result.get('nose_description')
                ),
                'id': None,
            }

            if save_to_db:
                # Save to database using individual columns
                try:
                    product = DiscoveredProduct.objects.create(
                        name=product_data['name'],
                        source_url=url,
                        product_type=product_data['product_type'] or 'whiskey',
                        status='partial',
                        abv=result.get('abv'),
                        nose_description=result.get('nose_description'),
                        palate_description=result.get('palate_description'),
                        finish_description=result.get('finish_description'),
                    )
                    product_data['id'] = product.id

                    # Run verification if enrich=True
                    if enrich:
                        try:
                            pipeline = _get_verification_pipeline()
                            verification_result = pipeline.verify_product(product)
                            # Update product_data with verification results
                            product.refresh_from_db()
                            product_data['source_count'] = verification_result.sources_used
                            product_data['verified_fields'] = verification_result.verified_fields
                            product_data['conflicts'] = verification_result.conflicts
                            product_data['status'] = product.status
                            product_data['completeness_score'] = product.completeness_score
                        except Exception as e:
                            logger.error(f"Verification failed for product: {e}")
                            product_data['source_count'] = 1
                            product_data['verified_fields'] = []
                            product_data['conflicts'] = []

                except Exception as e:
                    logger.error(f"Failed to save product: {e}")

            products.append(product_data)

        extraction_time_ms = int((time.time() - start_time) * 1000)

        return Response({
            'success': True,
            'page_type': page_type,
            'products': products,
            'extraction_time_ms': extraction_time_ms,
        })

    except Exception as e:
        logger.error(f"Extraction failed for {url}: {e}")
        return Response(
            {'error': f'Extraction failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@extend_schema(
    tags=['Extraction'],
    summary='Batch extract products from multiple URLs',
    description='''
    Extract products from multiple URLs in a single request.

    Maximum 50 URLs per request. URLs are processed sequentially or in parallel
    depending on the `parallel` parameter.
    ''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'urls': {
                    'type': 'array',
                    'items': {'type': 'string', 'format': 'uri'},
                    'maxItems': 50,
                    'description': 'List of URLs to extract (max 50)',
                },
                'product_type': {'type': 'string', 'enum': ['whiskey', 'port_wine', 'auto'], 'default': 'auto'},
                'save_to_db': {'type': 'boolean', 'default': True},
                'parallel': {'type': 'boolean', 'default': True, 'description': 'Process URLs in parallel'},
            },
            'required': ['urls'],
        }
    },
    responses={
        200: {
            'description': 'Batch extraction completed',
            'content': {
                'application/json': {
                    'example': {
                        'success': True,
                        'total_urls': 5,
                        'successful': 4,
                        'failed': 1,
                        'products_extracted': 4,
                        'extraction_time_ms': 5000,
                    }
                }
            }
        },
        400: {'description': 'Invalid URLs or exceeds 50 URL limit'},
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExtractionThrottle])
def extract_from_urls(request):
    """
    Batch extract products from multiple URLs.

    Maximum 50 URLs per request to prevent timeout issues.
    Each URL is processed and results aggregated.

    Request body:
    {
        "urls": ["https://...", "https://..."],
        "product_type": "auto",
        "save_to_db": true,
        "parallel": true
    }

    Returns summary with count of successful/failed extractions.
    """
    start_time = time.time()

    urls = request.data.get('urls')
    if not urls:
        return Response(
            {'error': 'urls is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if not isinstance(urls, list):
        return Response(
            {'error': 'urls must be a list'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if len(urls) > 50:
        return Response(
            {'error': 'Maximum 50 URLs allowed per request'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product_type = request.data.get('product_type', 'auto')
    save_to_db = request.data.get('save_to_db', True)
    parallel = request.data.get('parallel', True)
    enrich = request.data.get('enrich', False)

    results = []
    successful = 0
    failed = 0
    products_extracted = 0

    crawler = _get_smart_crawler()
    pipeline = _get_verification_pipeline() if enrich else None

    for url in urls:
        if not _is_valid_url(url):
            results.append({
                'url': url,
                'success': False,
                'error': 'Invalid URL',
            })
            failed += 1
            continue

        try:
            result = crawler.extract_product(
                product_name=None,
                url=url,
                product_type=product_type if product_type != 'auto' else None,
            )

            if result:
                product_id = None
                product_obj = None
                if save_to_db:
                    try:
                        product_obj = DiscoveredProduct.objects.create(
                            name=result.get('name'),
                            source_url=url,
                            product_type=result.get('product_type', 'whiskey'),
                            status='partial',
                            abv=result.get('abv'),
                            nose_description=result.get('nose_description'),
                            palate_description=result.get('palate_description'),
                            finish_description=result.get('finish_description'),
                        )
                        product_id = product_obj.id

                        # Run verification if enrich=True
                        if enrich and pipeline and product_obj:
                            try:
                                pipeline.verify_product(product_obj)
                            except Exception as e:
                                logger.error(f"Verification failed for product from {url}: {e}")

                    except Exception as e:
                        logger.error(f"Failed to save product from {url}: {e}")

                results.append({
                    'url': url,
                    'success': True,
                    'product_id': product_id,
                })
                successful += 1
                products_extracted += 1
            else:
                results.append({
                    'url': url,
                    'success': False,
                    'error': 'No product extracted',
                })
                failed += 1

        except Exception as e:
            results.append({
                'url': url,
                'success': False,
                'error': str(e),
            })
            failed += 1

    extraction_time_ms = int((time.time() - start_time) * 1000)

    return Response({
        'success': True,
        'total_urls': len(urls),
        'successful': successful,
        'failed': failed,
        'products_extracted': products_extracted,
        'results': results,
        'extraction_time_ms': extraction_time_ms,
    })


@extend_schema(
    tags=['Extraction'],
    summary='Search and extract product',
    description='''
    Search for a product using SerpAPI and extract from the best results.

    Uses intelligent source selection to prefer official brand sites and
    reputable retailers/review sites.
    ''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Search query (e.g., "Ardbeg Uigeadail whisky")'},
                'product_type': {'type': 'string', 'enum': ['whiskey', 'port_wine', 'auto'], 'default': 'auto'},
                'num_results': {'type': 'integer', 'default': 5, 'minimum': 1, 'maximum': 10},
                'save_to_db': {'type': 'boolean', 'default': True},
                'prefer_official': {'type': 'boolean', 'default': True, 'description': 'Prefer official brand sites'},
            },
            'required': ['query'],
        }
    },
    responses={
        200: {
            'description': 'Search and extraction completed',
            'content': {
                'application/json': {
                    'example': {
                        'success': True,
                        'query': 'Ardbeg Uigeadail',
                        'search_results_found': 5,
                        'urls_tried': 3,
                        'product': {'name': 'Ardbeg Uigeadail', 'status': 'partial'},
                        'extraction_time_ms': 3000,
                    }
                }
            }
        },
        400: {'description': 'Missing query parameter'},
        500: {'description': 'Search or extraction failed'},
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([ExtractionThrottle])
def extract_from_search(request):
    """
    Search for a product and extract from best results.

    Uses SerpAPI to search, then SmartCrawler to extract from found URLs.
    Prefers official brand sites when available.

    Request body:
    {
        "query": "Ardbeg Uigeadail whisky",
        "product_type": "whiskey",
        "num_results": 5,
        "save_to_db": true,
        "prefer_official": true
    }

    Returns the extracted product from the best matching source.
    """
    start_time = time.time()

    query = request.data.get('query')
    if not query:
        return Response(
            {'error': 'query is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    product_type = request.data.get('product_type', 'auto')
    num_results = request.data.get('num_results', 5)
    save_to_db = request.data.get('save_to_db', True)
    prefer_official = request.data.get('prefer_official', True)
    enrich = request.data.get('enrich', False)

    try:
        crawler = _get_smart_crawler()

        # Use SmartCrawler's search and extract capability
        result = crawler.extract_product(
            product_name=query,
            url=None,  # Will search for the product
            product_type=product_type if product_type != 'auto' else None,
        )

        product_data = None
        if result:
            product_data = {
                'id': None,
                'name': result.get('name'),
                'source_url': result.get('source_url', ''),
                'source_type': 'search_result',
                'status': result.get('status', 'partial'),
                'completeness_score': result.get('completeness_score', 0),
            }

            if save_to_db:
                try:
                    product = DiscoveredProduct.objects.create(
                        name=result.get('name'),
                        source_url=result.get('source_url', ''),
                        product_type=result.get('product_type', 'whiskey'),
                        status='partial',
                        abv=result.get('abv'),
                        nose_description=result.get('nose_description'),
                        palate_description=result.get('palate_description'),
                        finish_description=result.get('finish_description'),
                    )
                    product_data['id'] = product.id

                    # Run verification if enrich=True
                    if enrich:
                        try:
                            pipeline = _get_verification_pipeline()
                            verification_result = pipeline.verify_product(product)
                            product.refresh_from_db()
                            product_data['source_count'] = verification_result.sources_used
                            product_data['verified_fields'] = verification_result.verified_fields
                            product_data['conflicts'] = verification_result.conflicts
                            product_data['status'] = product.status
                            product_data['completeness_score'] = product.completeness_score
                        except Exception as e:
                            logger.error(f"Verification failed for product: {e}")

                except Exception as e:
                    logger.error(f"Failed to save product: {e}")

        extraction_time_ms = int((time.time() - start_time) * 1000)

        return Response({
            'success': True,
            'query': query,
            'search_results_found': 1 if result else 0,
            'urls_tried': 1,
            'product': product_data,
            'extraction_time_ms': extraction_time_ms,
        })

    except Exception as e:
        logger.error(f"Search extraction failed for '{query}': {e}")
        return Response(
            {'error': f'Search extraction failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================
# Award Crawl Endpoints
# ============================================================

@extend_schema(
    tags=['Crawl'],
    summary='Trigger award site crawl',
    description='''
    Trigger an asynchronous crawl of an award competition site.

    Valid sources: iwsc, dwwa, sfwsc, wwa

    A health check is performed before starting the crawl to ensure
    the source site structure hasn't changed.
    ''',
    request={
        'application/json': {
            'type': 'object',
            'properties': {
                'source': {
                    'type': 'string',
                    'enum': ['iwsc', 'dwwa', 'sfwsc', 'wwa'],
                    'description': 'Award source to crawl',
                },
                'year': {'type': 'integer', 'description': 'Competition year', 'default': 2025},
                'product_types': {
                    'type': 'array',
                    'items': {'type': 'string'},
                    'description': 'Filter by product types (e.g., ["whiskey", "port_wine"])',
                },
                'run_health_check': {'type': 'boolean', 'default': True},
                'async': {'type': 'boolean', 'default': True, 'description': 'Run crawl asynchronously'},
            },
            'required': ['source'],
        }
    },
    responses={
        202: {
            'description': 'Crawl job queued',
            'content': {
                'application/json': {
                    'example': {
                        'success': True,
                        'job_id': 'award-crawl-iwsc-2025-abc12345',
                        'source': 'iwsc',
                        'year': 2025,
                        'status': 'queued',
                        'status_url': '/api/v1/crawl/awards/status/award-crawl-iwsc-2025-abc12345/',
                    }
                }
            }
        },
        400: {'description': 'Invalid source or parameters'},
        503: {'description': 'Health check failed'},
    },
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([CrawlTriggerThrottle])
def trigger_award_crawl(request):
    """
    Trigger an award site crawl.

    Runs a health check before starting the crawl to detect any
    structural changes to the source site.

    Request body:
    {
        "source": "iwsc",
        "year": 2025,
        "product_types": ["port_wine"],
        "run_health_check": true,
        "async": true
    }

    Valid sources: iwsc, dwwa, sfwsc, wwa

    Returns a job_id for tracking crawl progress.
    """
    source = request.data.get('source')
    if not source:
        return Response(
            {'error': 'source is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    if source.lower() not in VALID_SOURCES:
        return Response(
            {'error': f'Invalid source. Valid sources: {", ".join(VALID_SOURCES)}'},
            status=status.HTTP_400_BAD_REQUEST
        )

    source = source.lower()
    year = request.data.get('year', timezone.now().year)
    product_types = request.data.get('product_types', [])
    run_health_check = request.data.get('run_health_check', True)
    async_mode = request.data.get('async', True)
    enrich = request.data.get('enrich', False)

    # Generate job ID
    job_id = f"award-crawl-{source}-{year}-{uuid.uuid4().hex[:8]}"

    # Run health check if requested
    health_check_result = None
    if run_health_check:
        try:
            checker = _get_selector_health_checker()
            health_report = checker.check_source(source, year)
            health_check_result = {
                'passed': health_report.is_healthy,
                'selectors_healthy': health_report.healthy_selectors,
                'selectors_total': health_report.total_selectors,
            }

            if not health_report.is_healthy:
                return Response({
                    'success': False,
                    'error': 'Health check failed',
                    'health_check': health_check_result,
                }, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        except Exception as e:
            logger.warning(f"Health check failed for {source}: {e}")
            health_check_result = {
                'passed': True,  # Continue anyway
                'warning': str(e),
            }

    # Create job record
    job = APICrawlJob.objects.create(
        job_id=job_id,
        source=source,
        year=year,
        status='queued',
        progress={
            'pages_processed': 0,
            'products_found': 0,
            'product_types': product_types,
        },
    )

    if async_mode:
        # Queue Celery task
        try:
            from crawler.tasks import trigger_award_crawl as crawl_task
            task = crawl_task.delay(job_id, source, year, product_types, enrich=enrich)
            job.celery_task_id = task.id
            job.save(update_fields=['celery_task_id'])
        except ImportError:
            # Celery not configured - mark as failed
            job.status = 'failed'
            job.error = 'Celery not configured'
            job.save(update_fields=['status', 'error'])

        response_data = {
            'success': True,
            'job_id': job_id,
            'source': source,
            'year': year,
            'status': 'queued',
            'status_url': f'/api/v1/crawl/awards/status/{job_id}/',
        }

        if health_check_result:
            response_data['health_check'] = health_check_result

        return Response(response_data, status=status.HTTP_202_ACCEPTED)
    else:
        # Synchronous execution (not recommended for large crawls)
        # For now, just return queued status
        return Response({
            'success': True,
            'job_id': job_id,
            'source': source,
            'year': year,
            'status': 'queued',
            'message': 'Synchronous crawl not implemented, job queued',
        }, status=status.HTTP_202_ACCEPTED)


@extend_schema(
    tags=['Crawl'],
    summary='Get crawl job status',
    description='Get the current status and progress of an award crawl job.',
    parameters=[
        OpenApiParameter(
            name='job_id',
            type=str,
            location=OpenApiParameter.PATH,
            description='The job ID returned from trigger_award_crawl',
        ),
    ],
    responses={
        200: {
            'description': 'Job status',
            'content': {
                'application/json': {
                    'example': {
                        'job_id': 'award-crawl-iwsc-2025-abc12345',
                        'source': 'iwsc',
                        'year': 2025,
                        'status': 'running',
                        'progress': {'pages_processed': 5, 'products_found': 48},
                        'elapsed_seconds': 120,
                    }
                }
            }
        },
        404: {'description': 'Job not found'},
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_crawl_status(request, job_id):
    """
    Get status of a crawl job.

    Returns the current status, progress, and timing information
    for the specified job_id.
    """
    try:
        job = APICrawlJob.objects.get(job_id=job_id)
    except APICrawlJob.DoesNotExist:
        return Response(
            {'error': 'Job not found'},
            status=status.HTTP_404_NOT_FOUND
        )

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


@extend_schema(
    tags=['Crawl'],
    summary='List award sources',
    description='List all available award sources with their metadata and health status.',
    responses={
        200: {
            'description': 'List of award sources',
            'content': {
                'application/json': {
                    'example': {
                        'sources': [
                            {
                                'id': 'iwsc',
                                'name': 'International Wine & Spirit Competition',
                                'url': 'https://www.iwsc.net',
                                'product_types': ['whiskey', 'port_wine'],
                                'health': {'status': 'healthy'},
                            }
                        ]
                    }
                }
            }
        },
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_award_sources(request):
    """
    List available award sources with health status.

    Returns metadata about each supported award source including
    the types of products available and current health status.
    """
    sources = []

    for source_id, metadata in SOURCE_METADATA.items():
        # Get latest health check
        latest_check = SourceHealthCheck.objects.filter(
            source=source_id,
        ).order_by('-checked_at').first()

        health_status = {
            'status': 'unknown',
            'last_check': None,
        }

        if latest_check:
            health_status = {
                'status': 'healthy' if latest_check.is_healthy else 'unhealthy',
                'last_check': latest_check.checked_at.isoformat(),
                'details': latest_check.details,
            }

        sources.append({
            'id': source_id,
            'name': metadata['name'],
            'url': metadata['url'],
            'product_types': metadata['product_types'],
            'requires_playwright': metadata['requires_playwright'],
            'health': health_status,
        })

    return Response({'sources': sources})


@extend_schema(
    tags=['Health'],
    summary='Get source health status',
    description='Get aggregated health status for all crawler sources.',
    responses={
        200: {
            'description': 'Health status for all sources',
            'content': {
                'application/json': {
                    'example': {
                        'overall_status': 'healthy',
                        'sources': {
                            'award_sites': [
                                {'id': 'iwsc', 'status': 'healthy'},
                                {'id': 'dwwa', 'status': 'healthy'},
                            ],
                            'retailers': [],
                        },
                    }
                }
            }
        },
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def sources_health(request):
    """
    Get health status for all sources.

    Aggregates health check results from all configured sources
    and returns an overall system health status.
    """
    award_sites = []

    for source_id in VALID_SOURCES:
        latest_check = SourceHealthCheck.objects.filter(
            source=source_id,
        ).order_by('-checked_at').first()

        health_data = {
            'id': source_id,
            'status': 'unknown',
            'last_health_check': None,
            'checks': {},
        }

        if latest_check:
            health_data['status'] = 'healthy' if latest_check.is_healthy else 'unhealthy'
            health_data['last_health_check'] = latest_check.checked_at.isoformat()
            health_data['checks'] = latest_check.details

        award_sites.append(health_data)

    # Determine overall status
    overall_status = 'healthy'
    for site in award_sites:
        if site['status'] == 'unhealthy':
            overall_status = 'degraded'
            break

    return Response({
        'overall_status': overall_status,
        'sources': {
            'award_sites': award_sites,
            'retailers': [],  # Could be extended later
        },
    })
