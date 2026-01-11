# Sections 9-11: Migration Plan, Benefits, and Files to Create/Modify

> **Source:** `FLOW_COMPARISON_ANALYSIS.md` lines 2250-2384

---

## 9. Migration Plan

### Phase 1: Core Infrastructure

1. **Create ProductCandidate dataclass**
   - `crawler/discovery/product_candidate.py`
   - Include all factory methods
   - Add completeness calculation with tasting = 40%

2. **Create ProductPipeline**
   - `crawler/services/product_pipeline.py`
   - Implement deduplication (reuse existing logic)
   - Implement save (wrap existing `save_discovered_product`)
   - Stub enrichment methods

3. **Update status model and add fields**
   - Add `INCOMPLETE`, `PARTIAL`, `COMPLETE`, `VERIFIED` to `DiscoveredProductStatus`
   - Add `completeness_score`, `source_count`, `verified_fields` to `DiscoveredProduct`
   - Add `palate_description`, `finish_description` to `DiscoveredProduct`
   - Create migrations

### Phase 2: Extractors & Orchestrators

1. **Create unified extractors**
   - `CompetitionExtractor` → produces `ProductCandidate`
   - `ListPageExtractor` → produces `ProductCandidate`
   - `SingleProductExtractor` → produces `ProductCandidate`

2. **Update orchestrators to use pipeline**
   - `CompetitionOrchestrator` → uses `ProductPipeline`
   - `DiscoveryOrchestrator` → uses `ProductPipeline`
   - `ContentProcessor` → uses `ProductPipeline`

### Phase 3: Multi-Source Verification

1. **Implement VerificationPipeline**
   - Search for additional sources when missing tasting data
   - Extract from 2-3 sources per product
   - Merge and verify data (matching values = verified)
   - Update `source_count` and `verified_fields`

2. **Implement smart enrichment in ProductPipeline**
   - `_enrich_from_link()` - if direct link available
   - `_enrich_from_search()` - targeted search for missing data
   - Only search for MISSING fields (not wasteful 3-search approach)

### Phase 4: Cleanup

1. **Remove legacy enrichment code**
   - Delete `SkeletonProductManager`
   - Delete `EnrichmentSearcher`
   - Delete skeleton-specific code from orchestrators
   - Remove SKELETON status handling

2. **Migrate data from JSON blobs**
   - Create data migration to move `extracted_data`, `enriched_data`, `taste_profile` to columns
   - Mark JSON fields as deprecated
   - Eventually remove JSON blob fields

3. **Update tests**
   - Create tests for `ProductCandidate`
   - Create tests for `ProductPipeline`
   - Create tests for `VerificationPipeline`
   - Test completeness calculation (especially tasting requirement)

---

## 10. Benefits of Unified Approach

| Aspect | Before | After |
|--------|--------|-------|
| **Code Paths** | 3 separate flows | 1 unified pipeline |
| **Product Creation** | 3 different implementations | 1 (`ProductPipeline.process`) |
| **Deduplication** | 3 implementations | 1 (in pipeline) |
| **Enrichment** | Always 3 SerpAPI calls | Smart, 0-2 targeted calls |
| **Status Model** | SKELETON/PENDING confusion | Clear completeness-based |
| **Maintainability** | Fix bugs in 3 places | Fix bugs in 1 place |
| **Testing** | Test 3 flows | Test 1 pipeline |
| **New Extractor** | Implement full flow | Just produce `ProductCandidate` |

---

## 11. Files to Create/Modify

### New Files

**Core Pipeline:**
- `crawler/discovery/product_candidate.py` - ProductCandidate dataclass with completeness calculation
- `crawler/services/product_pipeline.py` - Unified processing pipeline
- `crawler/services/verification_pipeline.py` - Multi-source verification pipeline

**Award Site URL Collectors:**
- `crawler/discovery/collectors/base_collector.py` - Base class for URL collectors
- `crawler/discovery/collectors/iwsc_collector.py` - IWSC URL collector (detail page URLs)
- `crawler/discovery/collectors/sfwsc_collector.py` - SFWSC URL collector
- `crawler/discovery/collectors/wwa_collector.py` - World Whiskies Awards URL collector
- `crawler/discovery/collectors/dwwa_collector.py` - Decanter WWA collector (Playwright-based, for Port wines)

**AI Extractors (unified):**
- `crawler/discovery/extractors/ai_extractor.py` - Unified AI extractor for all sources
- `crawler/discovery/extractors/extraction_prompts.py` - Extraction prompt templates

**Structural Change Detection:**
- `crawler/discovery/health/selector_health.py` - Pre-crawl selector health checker
- `crawler/discovery/health/yield_monitor.py` - Runtime yield monitoring
- `crawler/discovery/health/fingerprint.py` - Structural fingerprint computation and comparison
- `crawler/discovery/health/known_products.py` - Known product verification (ground truth)
- `crawler/discovery/health/alerts.py` - Alert handler (Sentry, Slack, email integration)
- `crawler/tasks/health_checks.py` - Celery tasks for scheduled health checks

**REST API:**
- `crawler/api/__init__.py` - API module init
- `crawler/api/views.py` - API view functions (extraction, crawl triggers, health)
- `crawler/api/urls.py` - API URL routing
- `crawler/api/serializers.py` - Request/response serializers
- `crawler/api/throttling.py` - Custom throttle classes
- `crawler/tasks/award_crawl.py` - Celery task for async award crawls

### Modified Files
- `crawler/models.py` - Add new statuses, `palate_description`, `finish_description`, `source_count`, `verified_fields`, `SourceHealthCheck`, `SourceFingerprint`, `CrawlJob` models
- `config/urls.py` - Include API URLs under `/api/v1/`
- `config/settings/base.py` - Add REST framework throttling configuration
- `crawler/services/competition_orchestrator.py` - Use URL collectors + AI extraction
- `crawler/services/discovery_orchestrator.py` - Simplify to use pipeline
- `crawler/services/content_processor.py` - Simplify to use pipeline
- `crawler/services/product_saver.py` - Update to handle new fields

### Deleted Files (after migration)
- `crawler/discovery/competitions/parsers.py` - Replaced by URL collectors + AI extraction
- `crawler/discovery/competitions/skeleton_manager.py` - No more skeleton products
- `crawler/discovery/competitions/enrichment_searcher.py` - Replaced by verification pipeline
- `crawler/discovery/enrichment/` (entire directory if no longer needed)

---
