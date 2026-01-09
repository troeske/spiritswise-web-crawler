# Crawler-AI Service V2 - Agent Quick Reference

## Spec Location

```
spiritswise-web-crawler/specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md
spiritswise-web-crawler/specs/CRAWLER_AI_SERVICE_V2_TASKS.md
```

## What This Is

A new architecture where:
- **AI Service** = Pure extraction engine (content-agnostic, receives full field schema)
- **Crawler** = Owns all quality decisions, orchestrates enrichment
- **Configuration** = Database-backed (ProductTypeConfig, FieldDefinition, QualityGateConfig, EnrichmentConfig)

## Key Requirements

1. **ABV is legally required** for PARTIAL and COMPLETE status (spirits labels)
2. **AI must recognize ABV synonyms**: ABV, Alcohol by Volume, Proof (divide by 2), Vol%, Alkoholgehalt, etc.
3. **Quality Gate Logic**: `STATUS = (ALL required_fields) AND (N or more from any_of_fields)`
4. **Source Tracking**: Store preprocessed content, archive to Wayback Machine, cleanup raw HTML after both complete

## Task Execution Order

### Start Here: Phase 0 Analysis Tasks
```
0.0.1 ANALYZE: Review existing models.py structure
0.0.2 ANALYZE: Map DiscoveredProduct, WhiskeyDetails, PortWineDetails fields
0.0.3 ANALYZE: Review existing admin.py patterns
```

### Then: Phase 0 Implementation (34 tasks)
- 0.1: Core Configuration Models
- 0.2: Django Admin Configuration
- 0.3: Schema Builder Service
- 0.4: Seed Initial Configuration Data

### Parallel Work Possible
- Phase 1 (AI Service V2) can run parallel with Phase 0
- Phase 2.5 (Content Preprocessing) can run parallel with Phase 0 & 1

## For Subagents

1. **Always read the spec first**: `specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md`
2. **Check task list for status**: `specs/CRAWLER_AI_SERVICE_V2_TASKS.md`
3. **Write tests BEFORE implementation** - TDD is mandatory
4. **Update task list** with status changes after each task
5. **Run tests** after each implementation task

## Subagent Assignments

| Subagent | Responsibility |
|----------|----------------|
| **Explore** | Analysis tasks (codebase review) |
| **crawler-dev** | Test writing and implementation |
| **test-runner** | Test execution and verification |
| **ai-service-dev** | AI Service development |
| **integration-dev** | Cross-service integration |

## Task Totals

| Metric | Count |
|--------|-------|
| Total Tasks | 241 |
| Tests | 115 |
| Implementation | 119 |
| Analysis | 7 |

## File Locations for Implementation

### Phase 0 Files
- `crawler/models/config.py` or `crawler/models.py` - Config models
- `crawler/admin.py` - Django Admin
- `crawler/services/config_service.py` - Schema builder
- `crawler/management/commands/seed_config.py` - Seed data
- `crawler/fixtures/*.json` - Configuration fixtures

### Phase 4 Source Tracking Files
- `crawler/models.py` - Add fields to CrawledSource
- `crawler/services/source_tracker.py` - Source tracking
- `crawler/services/wayback_service.py` - Wayback integration
- `crawler/management/commands/cleanup_raw_content.py` - Cleanup job
- `crawler/management/commands/archive_to_wayback.py` - Archive job
