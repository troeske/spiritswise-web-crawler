"""
Unified Product Pipeline Phase 6: API URL Configuration

URL patterns for the crawler REST API.

Endpoints:
- POST /api/v1/extract/url/          - Extract from single URL
- POST /api/v1/extract/urls/         - Batch extract from URLs
- POST /api/v1/extract/search/       - Search and extract
- POST /api/v1/crawl/awards/         - Trigger award crawl
- GET  /api/v1/crawl/awards/status/<job_id>/ - Get crawl status
- GET  /api/v1/crawl/awards/sources/ - List award sources
- GET  /api/v1/sources/health/       - Source health status
"""

from django.urls import path

from crawler.api.views import (
    extract_from_url,
    extract_from_urls,
    extract_from_search,
    trigger_award_crawl,
    get_crawl_status,
    list_award_sources,
    sources_health,
)

app_name = 'crawler_api'

urlpatterns = [
    # Extraction endpoints
    path('extract/url/', extract_from_url, name='extract_from_url'),
    path('extract/urls/', extract_from_urls, name='extract_from_urls'),
    path('extract/search/', extract_from_search, name='extract_from_search'),

    # Award crawl endpoints
    path('crawl/awards/', trigger_award_crawl, name='trigger_award_crawl'),
    path('crawl/awards/status/<str:job_id>/', get_crawl_status, name='get_crawl_status'),
    path('crawl/awards/sources/', list_award_sources, name='list_award_sources'),

    # Health endpoints
    path('sources/health/', sources_health, name='sources_health'),
]
