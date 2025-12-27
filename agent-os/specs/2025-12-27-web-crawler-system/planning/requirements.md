# Spec Requirements: Web Crawler System

## Initial Description

Build a comprehensive web crawler system for creating the world's most comprehensive whiskey and port wine database. The system addresses industry-specific challenges including age verification gates, anti-bot protections, and content preservation.

**Base Specification Document:** `C:\Users\tsroe\Documents_Local\Dev\Spiritswise\spiritswise-web-crawler\specs\web-crawler-spec-v3.md`

The spec v3 document contains:
- Age verification strategy (cookie injection + Playwright)
- Smart Router architecture (tiered fetching)
- Prestige-Led Discovery (competition-driven)
- Hub & Spoke Discovery (retailer-driven)
- Link Rot Mitigation (Wayback Machine)
- Database models (CrawlerSource, CrawlerKeyword, CrawledArticle, etc.)
- Technology stack and cost analysis

---

## Requirements Discussion

### First Round Questions

**Q1:** I see the spec outlines 5 phases with Phase 1 partially complete. I assume you want to proceed sequentially through phases, completing Phase 2 (Core Crawler) before moving to Phase 3 (Prestige Discovery). Is that correct, or should we prioritize certain high-value features earlier?
**Answer:** Implement all phases in one go (not sequential)

**Q2:** The spec mentions both whiskey and port wine support. Should we implement both product types in parallel, or focus on one category first?
**Answer:** Start with one category (whiskey), add port wine once core is stable

**Q3:** I notice the content_fetcher.py has Tier 1 (httpx) and Tier 2 (Playwright) implemented, but I don't see Tier 3 (ScrapingBee) integration. Should we implement all three tiers from the start, or add ScrapingBee only when we encounter sites that need it?
**Answer:** Implement all three tiers from the start

**Q4:** The spec mentions age gate cookie injection with hardcoded cookies per domain. I assume we want this stored in the database rather than in code. How should we handle updating these cookies when sites change their implementations?
**Answer:** Make a decision based on best practice

**Q5:** For the CrawledArticle model, I don't see this implemented yet. Should this be implemented as part of Phase 4, or should we add the model skeleton now for database schema stability?
**Answer:** Add the model skeleton now for schema stability

**Q6:** The spec mentions "Skeleton Products" created from competition data. Should these use a distinct status on DiscoveredProduct, or should we add a separate model?
**Answer:** Implement the most thorough and optimal approach

**Q7:** Should the crawler run as a Celery task in the same Django project (spiritswise-ai-enhancement-service) or as a separate microservice that calls the AI Enhancement API remotely?
**Answer:** Separate microservice (NOT in the AI Enhancement Service Django project)

**Q8:** The spec mentions using GPT-4 for extraction. Is this already configured in the AI Enhancement Service?
**Answer:** Use GPT-4 if it gives best results

**Q9:** For scheduling (Celery Beat), should there be a single periodic task that checks for due sources, or one scheduled task per active source?
**Answer:** Single periodic task that checks for due sources

**Q10:** The spec mentions monitoring & alerting via Sentry. Are there specific SLOs or thresholds you want to alert on?
**Answer:** Start with low SLOs/thresholds to verify implementation before scaling up

**Q11:** For link rot monitoring (weekly health checks on CrawledArticle), should this run as a scheduled background task, or defer to Phase 4?
**Answer:** Defer to Phase 4

**Q12:** Is there anything we should explicitly exclude from this initial implementation?
**Answer:** No exclusions (include paywalled, subscription, non-English sources)

**Q13 (New Requirement):** User indicated need for a dashboard UI to show results, status of crawls, human approval process, etc.

---

### Existing Code to Reference

No similar existing features identified for reference. This is a greenfield microservice.

**Note:** The AI Enhancement Service (`spiritswise-ai-enhancement-service`) contains existing implementations that inform this design:
- `ai_enhancement_engine/crawler_models.py` - Database models (to be migrated/shared)
- `ai_enhancement_engine/crawler_admin.py` - Admin customizations (patterns to follow)
- `ai_enhancement_engine/crawlers/` - Base crawler, content fetcher, URL frontier (reference implementations)
- `ai_enhancement_engine/views.py` - `/enhance/from-crawler/` endpoint (integration target)

These exist in the AI Enhancement Service but the crawler will be a separate microservice calling these APIs.

---

### Follow-up Questions

**Follow-up 1:** What frontend technology should we use for the dashboard?
**Answer:** Django Admin customizations (fastest to implement)

**Follow-up 2:** Who will access this dashboard?
**Answer:** Internal team only (simple Django auth)

**Follow-up 3:** Should the dashboard include Source Management, Cost Tracking, Error Logs, Manual Triggers?
**Answer:** Include ALL of these features

**Follow-up 4:** When a product is approved, what happens next (export, API push, direct write)?
**Answer:** Move to later phase (human approval workflow deferred)

**Follow-up 5:** Should reviewers be able to edit data, merge duplicates, bulk actions, add notes?
**Answer:** Move to later phase (human approval workflow deferred)

**Follow-up 6:** Should products be assigned to specific reviewers?
**Answer:** Move to later phase (human approval workflow deferred)

**Follow-up 7:** Where should the microservice live and should it use shared or isolated database?
**Answer:** Use existing `spiritswise-web-crawler/` repository, shared database with AI Enhancement Service (PostgreSQL)

---

## Visual Assets

### Files Provided:
No visual assets provided.

### Visual Insights:
N/A - No visuals to analyze.

---

## Requirements Summary

### Functional Requirements

**Core Crawling:**
- Multi-tiered content fetching: Tier 1 (httpx + cookies), Tier 2 (Playwright headless), Tier 3 (ScrapingBee)
- Smart Router that escalates through tiers on failure
- Age gate bypass via cookie injection (database-configurable per domain)
- Semantic age gate interaction (click "Enter Site" buttons via Playwright)
- robots.txt compliance checking
- Rate limiting per domain
- URL frontier queue management (Redis)

**Discovery Methods:**
- Hub & Spoke Discovery: Crawl retailer hubs to discover producer spokes
- Prestige-Led Discovery: Ingest competition results, create skeleton products, trigger targeted searches
- SerpAPI integration for Google Search discovery
- Keyword-based discovery with configurable search contexts

**Product Types:**
- Initial focus: Whiskey only
- Future addition: Port wine (after core is stable)

**Data Processing:**
- AI Enhancement Service integration via HTTP API (`/enhance/from-crawler/`)
- GPT-4 for extraction and enrichment (accuracy priority)
- Product deduplication via fingerprinting
- Skeleton product tracking for competition-discovered items

**Content Preservation:**
- CrawledArticle model for editorial content (schema added now, functionality in Phase 4)
- Article-Product many-to-many linking
- Wayback Machine archiving (deferred to Phase 4)
- Link rot health checks (deferred to Phase 4)

**Scheduling & Background Tasks:**
- Celery + Celery Beat for task management
- Single periodic task checks for due sources based on `crawl_frequency_hours`
- Manual crawl triggers from admin interface

**Dashboard (Django Admin Customizations):**
- Source Management: Add/edit/disable CrawlerSources
- Crawl Job Status: View running/completed/failed jobs with metrics
- Cost Tracking: Display API costs (SerpAPI, ScrapingBee, OpenAI) per day/week/month
- Error Logs: View recent failures with stack traces for debugging
- Manual Triggers: Trigger crawl for specific source on-demand
- Simple Django authentication for internal team access

**Monitoring:**
- Sentry integration for error tracking
- Start with low thresholds to verify implementation
- Track: failed fetches, blocked sites, age gate failures, API errors

---

### Architecture Decisions

**Microservice Architecture:**
- Separate Django microservice in `spiritswise-web-crawler/` repository
- Shared PostgreSQL database with AI Enhancement Service
- Calls AI Enhancement Service API remotely for content extraction/enrichment
- Own Redis instance for URL frontier queue
- Own Celery workers for crawl task execution

**Age Gate Cookie Management (Best Practice Decision):**
- Store cookies in database (`CrawlerSource.age_gate_cookies` field)
- Provide default fallback cookies for unknown sites
- Admin interface to update cookies when sites change
- Log age gate failures for manual cookie updates
- Consider future: automated cookie discovery via Playwright session capture

**Skeleton Products (Thorough Approach):**
- Add `status = 'skeleton'` choice to DiscoveredProduct model
- Skeleton products created from competition data with minimal info (name, award, year)
- Track `discovery_source` field: 'competition', 'hub_spoke', 'search', 'direct'
- Skeleton products trigger enrichment crawls to find full product data
- Match enriched data back to skeleton via fuzzy name matching

---

### Scope Boundaries

**In Scope (Initial Implementation):**
- All three fetching tiers (httpx, Playwright, ScrapingBee)
- Complete Smart Router with tier escalation
- Age gate cookie injection and semantic interaction
- Hub & Spoke discovery method
- Prestige-Led discovery (competition ingestion)
- SerpAPI integration
- CrawlerSource, CrawlerKeyword, CrawlJob, CrawledURL, DiscoveredProduct models
- CrawledArticle model skeleton (no functionality yet)
- Django Admin dashboard with:
  - Source management
  - Job status monitoring
  - Cost tracking
  - Error logs
  - Manual triggers
- Celery Beat scheduling (single task for due sources)
- AI Enhancement Service integration (HTTP API calls)
- Sentry monitoring with low initial thresholds
- Whiskey product type only

**Out of Scope (Deferred):**
- Port wine support (add after core stable)
- Human approval workflow (product review, editing, bulk actions)
- Reviewer assignment system
- Export/push of approved products to other services
- Link rot monitoring and health checks
- Wayback Machine archiving functionality
- Article content extraction and summarization
- High-volume SLOs and alerting thresholds

---

### Technical Considerations

**Technology Stack:**
- Framework: Django 4.2 + Django REST Framework
- Database: PostgreSQL (shared with AI Enhancement Service)
- Queue: Redis (URL frontier + Celery broker)
- Task Runner: Celery + Celery Beat
- HTTP Client: httpx with HTTP/2 support
- Headless Browser: Playwright (Chromium)
- Proxy Service: ScrapingBee
- Search API: SerpAPI
- AI: OpenAI GPT-4 (via AI Enhancement Service)
- Monitoring: Sentry

**Python Dependencies (from spec v3):**
```
httpx[http2]==0.27.0
playwright==1.40.0
beautifulsoup4==4.12.3
lxml==5.1.0
scrapingbee==1.1.2
waybackpy==3.0.6
tenacity==8.2.3
robotsparser==0.0.6
redis==5.0.0
celery==5.3.0
fuzzywuzzy==0.18.0
python-Levenshtein==0.25.0
trafilatura==1.6.3
sentry-sdk==1.39.0
```

**Integration Points:**
- AI Enhancement Service: `POST /api/v1/enhance/from-crawler/` for content extraction
- SerpAPI: Google Search for discovery queries
- ScrapingBee: Tier 3 fetching for blocked sites
- Wayback Machine: Future archiving (Phase 4)

**Database Schema Notes:**
- Models should match spec v3 definitions
- Add `status = 'skeleton'` to DiscoveredProductStatus choices
- Add `discovery_source` field to DiscoveredProduct
- Include CrawledArticle and ArticleProductMention models as skeletons
- Shared database means migrations must coordinate with AI Enhancement Service

**Cost Tracking Implementation:**
- Add `CrawlCost` model to track API usage per request
- Fields: `service` (serpapi/scrapingbee/openai), `cost_cents`, `crawl_job`, `timestamp`
- Aggregate in admin dashboard by day/week/month
- Display estimated vs actual costs

**Error Logging Implementation:**
- Add `CrawlError` model for persistent error tracking
- Fields: `source`, `url`, `error_type`, `message`, `stack_trace`, `timestamp`
- Display in admin with filtering by source, error type, date range
- Integrate with Sentry for real-time alerting

---

## Key Files from Spec v3 to Implement

| Component | Spec Section | Notes |
|-----------|--------------|-------|
| CrawlerSource model | 8.1 | Already exists in AI Enhancement Service, migrate/share |
| CrawlerKeyword model | 8.2 | Already exists, migrate/share |
| CrawledArticle model | 8.3 | Add as skeleton |
| ArticleProductMention model | 8.4 | Add as skeleton |
| DiscoveredProduct model | 8.5 | Already exists, add skeleton status |
| Smart Router | 10.1 | Implement full tier escalation |
| AI Enhancement Integration | 10.2 | HTTP client to existing API |
| Link Rot Pipeline | 10.3 | Defer to Phase 4 |
| Age Gate Cookies | 2.1 | Database-driven with defaults |
| Semantic Interaction | 2.2 | Playwright click solver |
| Hub & Spoke Discovery | 4.1 | Implement for whiskey hubs |
| Prestige Discovery | 4.2 | Competition parsing + skeleton products |
| Competition Configs | 5.3 | IWSC, SFWSC, WWA, Decanter |
| Whiskey Sources | 6.x | Seed data for initial sources |
| Keywords | 9.1 | Seed whiskey keywords |

---

## Estimated Monthly Costs (from spec v3)

| Service | Cost | Notes |
|---------|------|-------|
| SerpAPI | $75/mo | 5,000 searches |
| ScrapingBee | $49/mo | 100k requests |
| OpenAI GPT-4 | ~$100/mo | Via AI Enhancement Service |
| **Total** | **~$224/mo** | Excluding hosting |

Cost per product: ~$0.10 (vs $2-5 manual entry = 95-98% savings)
