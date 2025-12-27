# Specification: Web Crawler System

## Goal

Build a comprehensive web crawler microservice to create the world's most comprehensive whiskey database, handling industry-specific challenges including age verification gates, anti-bot protections, and multi-tiered content fetching with AI-powered extraction.

## User Stories

- As a data curator, I want to automatically discover and extract whiskey product data from retailers, producers, and review sites so that I can build a comprehensive database without manual data entry
- As an operations manager, I want to monitor crawl status, costs, and errors through a dashboard so that I can ensure the system operates efficiently and within budget

## Specific Requirements

**Multi-Tiered Content Fetching (Smart Router)**
- Implement three fetching tiers: Tier 1 (httpx + cookies), Tier 2 (Playwright headless), Tier 3 (ScrapingBee)
- Start with Tier 1 for all requests; escalate on failure (blocked, age gate detected, timeout)
- Mark domains requiring Tier 3 in database to skip lower tiers on subsequent requests
- Persist discovered session cookies to Redis for future domain requests
- Implement exponential backoff retry logic with configurable max retries

**Age Gate Bypass System**
- Store age gate cookies per domain in `CrawlerSource.age_gate_cookies` JSONField
- Provide default fallback cookies for unknown sites (age_verified, dob, over18, etc.)
- Detect age gates by content length < 500 chars or keywords ("Legal Drinking Age", "Are you 21")
- Implement Playwright click solver for semantic interaction (match buttons: "Yes", "Enter", "I am 21+", "Confirm")
- Log age gate failures for manual cookie updates via admin interface

**Hub and Spoke Discovery**
- Crawl retailer hub sites (thewhiskyexchange.com/brands, masterofmalt.com/brands, whiskybase.com/distilleries)
- Extract brand names and external producer links from hub pages
- Query SerpAPI for producer official sites when no direct link found
- Validate discovered domains and add to CrawlerSource with discovery_method='hub'

**Prestige-Led Discovery (Competition-Driven)**
- Parse competition results from IWSC, SFWSC, World Whiskies Awards, Decanter WWA
- Create skeleton products (status='skeleton') from competition data with minimal info (name, award, year)
- Trigger 3 SerpAPI searches per skeleton: price/buy, review/tasting notes, official site
- Queue discovered URLs with priority=10 (highest) for immediate processing
- Match enriched data back to skeleton via fuzzy name matching (fuzzywuzzy)

**Database Models**
- Extend existing models from AI Enhancement Service with shared PostgreSQL database
- Add `status='skeleton'` choice and `discovery_source` field to DiscoveredProduct model
- Add `age_gate_type`, `age_gate_cookies`, `requires_tier3` fields to CrawlerSource model
- Create CrawledArticle and ArticleProductMention skeleton models (functionality deferred)
- Add CrawlCost model for API usage tracking (service, cost_cents, crawl_job, timestamp)
- Add CrawlError model for persistent error logging (source, url, error_type, stack_trace, timestamp)

**AI Enhancement Service Integration**
- Call existing `/api/v1/enhance/from-crawler/` endpoint via HTTP for content extraction
- Use GPT-4 for extraction accuracy (configured in AI Enhancement Service)
- Send crawled content with source_url and product_type_hint for processing
- Store extraction results in DiscoveredProduct.extracted_data and enriched_data JSONFields

**Celery Task Scheduling**
- Single periodic task runs every 5 minutes to check for due sources (next_crawl_at <= now)
- Create CrawlJob for each due source and dispatch to Celery worker queue
- Separate task queue for keyword-based SerpAPI searches (search_frequency_hours)
- Manual crawl triggers create CrawlJob entries processed by same worker pool

**Django Admin Dashboard**
- Source Management: CRUD for CrawlerSources with fieldsets for identity, crawl config, technical requirements, compliance
- Cost Tracking: Display aggregated API costs by day/week/month with service breakdown (SerpAPI, ScrapingBee, OpenAI)
- Error Logs: Filterable list of CrawlError records with source, error type, date range filters
- Manual Triggers: Admin actions to trigger immediate crawl for selected sources
- Job Status: List view of CrawlJobs with status badges, metrics (pages, products, errors), duration display

**Monitoring and Error Handling**
- Integrate Sentry SDK for real-time error tracking and alerting
- Set initial low thresholds: alert on >5 consecutive failures per source, >10% error rate per day
- Track: failed fetches (by tier), blocked sites, age gate failures, API errors, rate limit hits
- Log detailed error context (URL, source, tier used, response status, headers) for debugging

## Visual Design

No visual mockups provided. Dashboard uses Django Admin with standard list/detail views plus custom admin actions and badge displays for status indicators.

## Existing Code to Leverage

**AI Enhancement Service crawler_models.py**
- Contains CrawlerSource, CrawlerKeyword, CrawlJob, CrawledURL, DiscoveredProduct models
- Use as reference for model structure; migrate to shared database access pattern
- Extend DiscoveredProductStatus choices with 'skeleton' status
- Reuse fingerprint computation and content hash methods

**AI Enhancement Service crawler_admin.py**
- Contains admin configurations with status badges, fieldsets, custom actions
- Replicate badge styling pattern (colored spans for status, active, confidence)
- Copy admin action patterns: trigger_crawl, disable/enable sources, reset schedule
- Follow fieldset organization (Identity, Config, Technical, Compliance, Status, Metadata)

**AI Enhancement Service content_fetcher.py**
- Implements Tier 1 (httpx) and Tier 2 (Playwright) fetching with async context manager
- Extend with Tier 3 ScrapingBee integration and age gate detection logic
- Reuse DEFAULT_HEADERS, retry logic with exponential backoff, lazy Playwright initialization
- Add cookie injection and session persistence capabilities

**AI Enhancement Service url_frontier.py**
- Redis-based priority queue with URL deduplication via sorted sets
- Reuse queue patterns, seen URL tracking, priority inversion logic
- Extend with domain-specific cookie caching keys
- Use same Redis key patterns for consistency

**AI Enhancement Service views.py**
- Contains `/enhance/from-crawler/` endpoint as integration target
- Crawler calls this endpoint remotely via httpx async client
- Use same request/response JSON structure for content submission

## Out of Scope

- Port wine support (add after whiskey core is stable and validated)
- Human approval workflow (product review UI, editing, bulk approve/reject actions)
- Reviewer assignment system (assigning products to specific reviewers)
- Export/push of approved products to external services or inventory systems
- Link rot monitoring and health checks for CrawledArticles
- Wayback Machine archiving functionality for content preservation
- Article content extraction, summarization, and product linking
- High-volume SLOs and production alerting thresholds (start with low thresholds)
- Paywalled or subscription-gated content handling (include in source config but defer implementation)
- Non-English source handling (include in source config but defer implementation)
