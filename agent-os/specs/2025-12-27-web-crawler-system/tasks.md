# Task Breakdown: Web Crawler System

## Overview
Total Tasks: 78 sub-tasks across 10 task groups

This task breakdown implements the Web Crawler System as a separate Django microservice in the `spiritswise-web-crawler` repository, sharing a PostgreSQL database with the AI Enhancement Service.

## Task List

---

### Project Setup & Infrastructure

#### Task Group 1: Django Project Initialization
**Dependencies:** None

- [x] 1.0 Complete Django project setup
  - [x] 1.1 Initialize Django project structure
    - Create `spiritswise-web-crawler/` Django project
    - Create `crawler/` Django app
    - Configure `settings.py` for shared PostgreSQL database
    - Set up environment variables (DATABASE_URL, REDIS_URL, API keys)
  - [x] 1.2 Configure Python dependencies
    - Create `requirements.txt` with all dependencies:
      - Django 4.2, Django REST Framework
      - httpx[http2]==0.27.0, playwright==1.40.0
      - beautifulsoup4==4.12.3, lxml==5.1.0
      - scrapingbee==1.1.2, tenacity==8.2.3
      - robotsparser==0.0.6, redis==5.0.0
      - celery==5.3.0, fuzzywuzzy==0.18.0
      - python-Levenshtein==0.25.0, trafilatura==1.6.3
      - sentry-sdk==1.39.0
  - [x] 1.3 Configure Celery for task processing
    - Set up `celery.py` with Redis broker
    - Configure Celery Beat scheduler
    - Create separate task queues: `crawl`, `search`
  - [x] 1.4 Configure Sentry integration
    - Install and configure sentry-sdk
    - Set environment-based DSN
    - Configure sample rate and error filtering
  - [x] 1.5 Verify project initialization
    - Run Django check command
    - Verify Celery worker starts
    - Verify Redis connection

**Acceptance Criteria:**
- Django project runs with `python manage.py runserver`
- Celery worker connects to Redis
- Sentry captures test exception
- All dependencies install successfully

---

### Database Layer

#### Task Group 2: Database Models & Migrations
**Dependencies:** Task Group 1

- [x] 2.0 Complete database layer
  - [x] 2.1 Write 4-6 focused tests for model functionality
    - Test CrawlerSource `is_due_for_crawl()` method
    - Test DiscoveredProduct fingerprint computation
    - Test CrawlJob status transitions
    - Test CrawlCost aggregation query
  - [x] 2.2 Extend CrawlerSource model
    - Add `age_gate_type` field (choices: none, cookie, click, form)
    - Add `age_gate_cookies` JSONField for per-domain cookies
    - Add `requires_tier3` BooleanField (marks ScrapingBee requirement)
    - Add `discovery_method` field (choices: hub, search, competition, manual)
    - Reference pattern from: `ai_enhancement_engine/crawler_models.py`
  - [x] 2.3 Extend DiscoveredProduct model
    - Add `SKELETON = 'skeleton', 'Skeleton (needs enrichment)'` to DiscoveredProductStatus
    - Add `discovery_source` field (choices: competition, hub_spoke, search, direct)
    - Add `awards` JSONField for competition data storage
  - [x] 2.4 Create CrawledArticle model skeleton
    - Fields: id, source, original_url, title, author, published_date
    - Fields: summary_bullets, extracted_tags, sentiment_score (JSONField)
    - Fields: local_snapshot_path, wayback_url, is_original_live, last_health_check
    - Fields: discovered_at (auto_now_add)
    - Add unique constraint on original_url
  - [x] 2.5 Create ArticleProductMention model skeleton
    - Fields: article (FK), product (FK), mention_type, rating_score, rating_scale, excerpt
    - Add unique_together constraint on (article, product)
  - [x] 2.6 Create CrawlCost model for API usage tracking
    - Fields: id, service (serpapi/scrapingbee/openai), cost_cents (IntegerField)
    - Fields: crawl_job (FK), request_count, timestamp
    - Add indexes for aggregation queries (service, timestamp)
  - [x] 2.7 Create CrawlError model for persistent error logging
    - Fields: id, source (FK), url, error_type, message, stack_trace
    - Fields: tier_used, response_status, response_headers (JSONField)
    - Fields: timestamp, resolved (BooleanField)
    - Add indexes for filtering (source, error_type, timestamp)
  - [x] 2.8 Create and run migrations
    - Generate migrations for all new/modified models
    - Coordinate with AI Enhancement Service migrations
    - Add data migration for existing CrawlerSource records (set defaults)
  - [x] 2.9 Ensure database layer tests pass
    - Run ONLY the 4-6 tests written in 2.1
    - Verify migrations run without errors

**Acceptance Criteria:**
- All 4-6 tests from 2.1 pass
- Migrations apply successfully to shared database
- Model relationships work correctly
- Indexes created for query performance

---

### Content Fetching Layer

#### Task Group 3: Multi-Tiered Smart Router
**Dependencies:** Task Group 2

- [x] 3.0 Complete content fetching system
  - [x] 3.1 Write 4-6 focused tests for fetching tiers
    - Test Tier 1 httpx with cookie injection
    - Test age gate detection logic (content length < 500, keyword detection)
    - Test tier escalation on failure
    - Test `requires_tier3` marking on successful Tier 3 fetch
  - [x] 3.2 Implement Tier 1 fetcher (httpx + cookies)
    - Async httpx client with HTTP/2 support
    - Cookie injection from CrawlerSource.age_gate_cookies
    - Default fallback cookies for unknown domains
    - Configurable timeout and retry logic
    - Reference: `ai_enhancement_engine/crawlers/content_fetcher.py`
  - [x] 3.3 Implement Tier 2 fetcher (Playwright headless)
    - Lazy Playwright initialization (import on first use)
    - Age gate semantic click solver
    - Match buttons: "Yes", "Enter", "I am 21+", "I am 18+", "Confirm", "Agree", "Enter Site"
    - Session cookie persistence to Redis
    - Reference: `ai_enhancement_engine/crawlers/content_fetcher.py`
  - [x] 3.4 Implement Tier 3 fetcher (ScrapingBee)
    - ScrapingBee API client integration
    - Premium proxy and JavaScript rendering options
    - Cost tracking per request (create CrawlCost record)
    - Mark domain `requires_tier3 = True` on success
  - [x] 3.5 Implement Smart Router orchestration
    - Check `requires_tier3` flag to skip lower tiers
    - Tier escalation: Tier 1 -> Tier 2 -> Tier 3
    - Age gate detection: content length < 500 chars or keywords detected
    - Exponential backoff retry logic (tenacity)
    - Log failures to CrawlError model
  - [x] 3.6 Implement age gate detection utilities
    - Content length threshold check (< 500 chars)
    - Keyword detection: "Legal Drinking Age", "Are you 21", "Age Verification", "Are you of legal drinking age"
    - Return detection result with reason
  - [x] 3.7 Ensure content fetching tests pass
    - Run ONLY the 4-6 tests written in 3.1
    - Verify all three tiers work independently

**Acceptance Criteria:**
- All 4-6 tests from 3.1 pass
- Tier 1 injects cookies correctly
- Tier 2 clicks age gate buttons
- Tier 3 integrates with ScrapingBee API
- Smart Router escalates appropriately

---

### Discovery Systems

#### Task Group 4: Hub & Spoke Discovery
**Dependencies:** Task Group 3

- [x] 4.0 Complete Hub & Spoke discovery
  - [x] 4.1 Write 3-4 focused tests for hub discovery
    - Test hub page parsing for brand extraction
    - Test SerpAPI fallback query generation
    - Test CrawlerSource creation with discovery_method='hub'
  - [x] 4.2 Implement hub page crawler
    - Target hubs: thewhiskyexchange.com/brands, masterofmalt.com/brands, whiskybase.com/distilleries
    - Parse brand/producer listings
    - Extract external producer links where available
    - Handle pagination for large lists
  - [x] 4.3 Implement SerpAPI client
    - Google Search API integration
    - Query format: "{Brand Name} official site whiskey"
    - Parse search results for official domain
    - Cost tracking per search (create CrawlCost record)
  - [x] 4.4 Implement spoke validation and registration
    - Validate discovered domains (check reachability)
    - Create CrawlerSource with discovery_method='hub'
    - Set initial crawl configuration defaults
    - Prevent duplicate source creation
  - [x] 4.5 Ensure Hub & Spoke tests pass
    - Run ONLY the 3-4 tests written in 4.1

**Acceptance Criteria:**
- All 3-4 tests from 4.1 pass
- Hub pages parse correctly
- SerpAPI queries return valid results
- New sources created with correct metadata

---

#### Task Group 5: Prestige-Led Discovery (Competitions)
**Dependencies:** Task Groups 3, 4

- [x] 5.0 Complete Prestige-Led discovery
  - [x] 5.1 Write 4-5 focused tests for competition parsing
    - Test skeleton product creation from competition data
    - Test SerpAPI triple search trigger (price, review, official)
    - Test fuzzy name matching for skeleton enrichment
    - Test priority queue insertion (priority=10)
  - [x] 5.2 Implement competition parsers
    - IWSC parser: `iwsc.net/results/search/{year}`
    - SFWSC parser: `thetastingalliance.com/results/`
    - World Whiskies Awards parser: `worldwhiskiesawards.com/winners`
    - Decanter WWA parser: `awards.decanter.com` (filter by Port)
    - Extract: product name, medal/award, year, producer
  - [x] 5.3 Implement skeleton product creation
    - Create DiscoveredProduct with status='skeleton'
    - Set discovery_source='competition'
    - Store awards in JSONField: [{"competition": "IWSC", "year": 2024, "medal": "Gold"}]
    - Set minimal extracted_data (name, award info only)
  - [x] 5.4 Implement enrichment search triggers
    - Trigger 3 SerpAPI searches per skeleton:
      - "{Product Name} price buy online"
      - "{Product Name} review tasting notes"
      - "{Product Name} official site"
    - Queue discovered URLs with priority=10 (highest)
  - [x] 5.5 Implement fuzzy matching for enrichment
    - Use fuzzywuzzy for name matching
    - Match threshold: 85% similarity
    - Update skeleton product with enriched data
    - Change status from 'skeleton' to 'pending'
  - [x] 5.6 Ensure Prestige-Led tests pass
    - Run ONLY the 4-5 tests written in 5.1

**Acceptance Criteria:**
- All 4-5 tests from 5.1 pass
- Competition pages parse correctly
- Skeleton products created with award data
- SerpAPI searches trigger for each skeleton
- Fuzzy matching enriches skeleton products

---

### Task Scheduling & Queue Management

#### Task Group 6: Celery Tasks & URL Frontier
**Dependencies:** Task Groups 3, 4, 5

- [x] 6.0 Complete task scheduling system
  - [x] 6.1 Write 3-4 focused tests for task scheduling
    - Test due source detection (next_crawl_at <= now)
    - Test CrawlJob creation and status transitions
    - Test URL frontier priority queue ordering
  - [x] 6.2 Implement URL Frontier (Redis-based)
    - Priority queue using Redis sorted sets
    - URL deduplication via seen URL tracking
    - Domain-specific cookie caching keys
    - Priority inversion (lower number = higher priority)
    - Reference: `ai_enhancement_engine/crawlers/url_frontier.py`
  - [x] 6.3 Implement periodic source check task
    - Celery Beat task running every 5 minutes
    - Query CrawlerSource where `is_active=True AND next_crawl_at <= now()`
    - Create CrawlJob for each due source
    - Dispatch to `crawl` queue
  - [x] 6.4 Implement crawl worker task
    - Fetch URLs from source via Smart Router
    - Send content to AI Enhancement Service
    - Create/update DiscoveredProduct records
    - Update CrawlJob metrics (pages_crawled, products_found, etc.)
    - Handle errors gracefully (create CrawlError records)
  - [x] 6.5 Implement keyword search task
    - Celery Beat task for keyword-based SerpAPI searches
    - Query CrawlerKeyword where `is_active=True AND next_search_at <= now()`
    - Execute searches and queue discovered URLs
    - Dispatch to `search` queue
  - [x] 6.6 Implement manual crawl trigger task
    - Accept source_id parameter
    - Create CrawlJob and dispatch immediately
    - Return job_id for status tracking
  - [x] 6.7 Ensure task scheduling tests pass
    - Run ONLY the 3-4 tests written in 6.1

**Acceptance Criteria:**
- All 3-4 tests from 6.1 pass
- Periodic task discovers due sources
- CrawlJobs created and processed
- URL frontier maintains priority ordering
- Manual triggers work immediately

---

### AI Enhancement Integration

#### Task Group 7: AI Enhancement Service Integration
**Dependencies:** Task Groups 3, 6

- [x] 7.0 Complete AI Enhancement Service integration
  - [x] 7.1 Write 2-3 focused tests for AI integration
    - Test HTTP client request formatting
    - Test response parsing and DiscoveredProduct update
    - Test error handling for API failures
  - [x] 7.2 Implement AI Enhancement API client
    - Async httpx client for `/api/v1/enhance/from-crawler/` endpoint
    - Request format: { content, source_url, product_type_hint }
    - Authentication via Bearer token
    - Configurable timeout (60s default)
    - Reference: `ai_enhancement_engine/views.py`
  - [x] 7.3 Implement content processing pipeline
    - Clean raw HTML content (trafilatura extraction)
    - Determine product_type_hint from CrawlerSource.product_types
    - Call AI Enhancement Service
    - Parse response and update DiscoveredProduct.extracted_data
  - [x] 7.4 Implement cost tracking for AI calls
    - Create CrawlCost record for each AI Enhancement call
    - Service: 'openai', cost estimated from token usage
    - Link to CrawlJob for aggregation
  - [x] 7.5 Ensure AI integration tests pass
    - Run ONLY the 2-3 tests written in 7.1

**Acceptance Criteria:**
- All 2-3 tests from 7.1 pass
- API client formats requests correctly
- Responses update DiscoveredProduct
- Cost tracking records created

---

### Django Admin Dashboard

#### Task Group 8: Admin Dashboard & Source Management
**Dependencies:** Task Groups 2, 6

- [x] 8.0 Complete Django Admin dashboard
  - [x] 8.1 Write 2-3 focused tests for admin functionality
    - Test trigger_crawl admin action
    - Test cost aggregation display
    - Test error log filtering
  - [x] 8.2 Implement CrawlerSource admin
    - Fieldsets: Identity, Classification, Crawl Config, Age Gate, Technical, Compliance, Status
    - List display: name, category, is_active, priority, last_crawl_at, total_products_found
    - List filters: is_active, category, age_gate_type, requires_tier3
    - Search fields: name, base_url
    - Actions: trigger_crawl, enable_sources, disable_sources, reset_schedule
    - Status badges (colored spans) for is_active and last_crawl_status
    - Reference: `ai_enhancement_engine/crawler_admin.py`
  - [x] 8.3 Implement CrawlJob admin
    - List display: source, status, started_at, completed_at, pages_crawled, products_found, errors_count
    - List filters: status, source, created_at date range
    - Status badges for job status (pending=yellow, running=blue, completed=green, failed=red)
    - Duration display (formatted seconds/minutes)
    - Read-only for most fields (jobs created programmatically)
  - [x] 8.4 Implement Cost Tracking admin view
    - Custom admin view for cost aggregation
    - Display costs by day/week/month
    - Breakdown by service (SerpAPI, ScrapingBee, OpenAI)
    - Chart visualization (optional - basic table sufficient for MVP)
  - [x] 8.5 Implement CrawlError admin
    - List display: source, url (truncated), error_type, timestamp, resolved
    - List filters: source, error_type, resolved, timestamp date range
    - Search fields: url, message
    - Detail view with full stack_trace and response_headers
    - Action: mark_resolved
  - [x] 8.6 Implement DiscoveredProduct admin
    - List display: name (from extracted_data), product_type, status, source, discovered_at
    - List filters: status, product_type, discovery_source
    - Status badges for product status
    - Actions: approve_products, reject_products, mark_duplicate
    - JSON pretty-print for extracted_data and enriched_data fields
  - [x] 8.7 Implement CrawlerKeyword admin
    - List display: keyword, search_context, is_active, priority, last_searched_at
    - List filters: is_active, search_context, product_types
    - Actions: trigger_search, enable_keywords, disable_keywords
  - [x] 8.8 Ensure admin tests pass
    - Run ONLY the 2-3 tests written in 8.1

**Acceptance Criteria:**
- All 2-3 tests from 8.1 pass
- All admin interfaces render correctly
- Admin actions work as expected
- Cost tracking displays aggregated data
- Error logs filterable and searchable

---

### Monitoring & Error Handling

#### Task Group 9: Monitoring & Alerting
**Dependencies:** Task Groups 3, 6, 8

- [x] 9.0 Complete monitoring system
  - [x] 9.1 Write 2-3 focused tests for monitoring
    - Test Sentry error capture
    - Test consecutive failure threshold detection
    - Test CrawlError record creation
  - [x] 9.2 Implement Sentry error tracking
    - Configure Sentry SDK in settings (already done in Task Group 1)
    - Set sample rate for performance monitoring
    - Add breadcrumbs for crawl context (source, URL, tier)
    - Filter sensitive data (cookies, API keys)
  - [x] 9.3 Implement consecutive failure tracking
    - Track failures per source in Redis
    - Alert threshold: 5 consecutive failures
    - Trigger Sentry alert on threshold breach
    - Reset counter on successful crawl
  - [x] 9.4 Implement daily error rate monitoring
    - Calculate error rate per day (errors / total requests)
    - Alert threshold: > 10% error rate
    - Log alert to Sentry
  - [x] 9.5 Implement detailed error context logging
    - Log: URL, source, tier_used, response_status, headers
    - Create CrawlError record for every failure
    - Include stack trace for exceptions
  - [x] 9.6 Ensure monitoring tests pass
    - Run ONLY the 2-3 tests written in 9.1

**Acceptance Criteria:**
- All 2-3 tests from 9.1 pass
- Sentry captures errors with context
- Alerts trigger on threshold breach
- CrawlError records created for all failures

---

### Testing & Finalization

#### Task Group 10: Test Review & Gap Analysis
**Dependencies:** Task Groups 1-9

- [x] 10.0 Review existing tests and fill critical gaps only
  - [x] 10.1 Review tests from Task Groups 1-9
    - Review tests from Task Group 2 (database layer): 4-6 tests
    - Review tests from Task Group 3 (content fetching): 4-6 tests
    - Review tests from Task Group 4 (hub discovery): 3-4 tests
    - Review tests from Task Group 5 (prestige discovery): 4-5 tests
    - Review tests from Task Group 6 (task scheduling): 3-4 tests
    - Review tests from Task Group 7 (AI integration): 2-3 tests
    - Review tests from Task Group 8 (admin): 2-3 tests
    - Review tests from Task Group 9 (monitoring): 2-3 tests
    - Total existing tests: approximately 24-34 tests
  - [x] 10.2 Analyze test coverage gaps for crawler feature only
    - Identify critical user workflows lacking coverage
    - Focus on end-to-end crawl workflow
    - Prioritize integration points (AI Service, SerpAPI, ScrapingBee)
  - [x] 10.3 Write up to 10 additional strategic tests maximum
    - End-to-end: Full crawl cycle (source -> fetch -> AI -> product)
    - Integration: AI Enhancement Service response handling
    - Integration: SerpAPI rate limiting
    - Error handling: Graceful degradation on API failures
    - Database: DiscoveredProduct deduplication via fingerprint
  - [x] 10.4 Create seed data fixtures
    - Initial CrawlerSources for whiskey retailers/producers
    - Initial CrawlerKeywords for whiskey discovery
    - Competition source configurations (IWSC, SFWSC, WWA, Decanter)
  - [x] 10.5 Run feature-specific tests only
    - Run ALL tests written for this feature (approximately 34-44 tests)
    - Verify critical workflows pass
    - Do NOT run tests from other services

**Acceptance Criteria:**
- All feature-specific tests pass (approximately 34-44 tests total)
- Critical user workflows covered
- No more than 10 additional tests added
- Seed data fixtures created and loadable

---

## Execution Order

Recommended implementation sequence:

1. **Project Setup** (Task Group 1) - Django project, dependencies, Celery, Sentry
2. **Database Layer** (Task Group 2) - Models, migrations, shared database setup
3. **Content Fetching** (Task Group 3) - Smart Router with 3 tiers
4. **Hub & Spoke Discovery** (Task Group 4) - Retailer-driven discovery
5. **Prestige-Led Discovery** (Task Group 5) - Competition-driven skeleton products
6. **Task Scheduling** (Task Group 6) - Celery tasks, URL frontier
7. **AI Integration** (Task Group 7) - AI Enhancement Service client
8. **Admin Dashboard** (Task Group 8) - Django Admin customizations
9. **Monitoring** (Task Group 9) - Sentry, error tracking, alerts
10. **Test Review** (Task Group 10) - Gap analysis, additional tests, fixtures

---

## Technical Notes

### Shared Database Configuration
The crawler microservice shares a PostgreSQL database with the AI Enhancement Service. Migrations must be coordinated to avoid conflicts. Use Django's `--database` flag if needed for migration management.

### Redis Usage
- **URL Frontier**: Priority queue for crawl URLs
- **Session Cookies**: Cache discovered session cookies by domain
- **Celery Broker**: Task queue messaging
- **Failure Tracking**: Consecutive failure counters per source

### Cost Tracking
All external API calls (SerpAPI, ScrapingBee, OpenAI via AI Service) should create CrawlCost records for budget monitoring and ROI calculation.

### Reference Files
- Model patterns: `spiritswise-ai-enhancement-service/ai_enhancement_engine/crawler_models.py`
- Admin patterns: `spiritswise-ai-enhancement-service/ai_enhancement_engine/crawler_admin.py`
- Fetcher patterns: `spiritswise-ai-enhancement-service/ai_enhancement_engine/crawlers/content_fetcher.py`
- URL Frontier patterns: `spiritswise-ai-enhancement-service/ai_enhancement_engine/crawlers/url_frontier.py`

### Out of Scope (Deferred)
- Port wine support (add after whiskey core is stable)
- Human approval workflow (product review UI, editing, bulk actions)
- Reviewer assignment system
- Export/push of approved products
- Link rot monitoring and health checks
- Wayback Machine archiving functionality
- Article content extraction and summarization
- High-volume SLOs and alerting thresholds
