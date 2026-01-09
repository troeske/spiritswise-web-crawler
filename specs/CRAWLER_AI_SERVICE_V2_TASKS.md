# Crawler-AI Service Architecture V2 - Implementation Tasks

**Spec Reference**: `specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md`
**Created**: 2026-01-09
**Status**: PENDING REVIEW

---

## Implementation Guidelines

### TDD Approach (MANDATORY)

For ALL implementation tasks:
1. **Write tests FIRST** - Define expected behavior before implementation
2. **Run tests** - Confirm they fail (red)
3. **Implement** - Write minimal code to pass tests
4. **Refactor** - Clean up while tests pass (green)
5. **Document** - Update docstrings and comments

### Status Tracking

Each task uses these statuses:
- `[ ]` NOT STARTED
- `[T]` TESTS WRITTEN (waiting for implementation)
- `[P]` IN PROGRESS
- `[R]` IN REVIEW
- `[X]` COMPLETE
- `[B]` BLOCKED (with reason)

### Subagent Assignment

Tasks are assigned to specialized subagents:
- **ai-service-dev**: AI Enhancement Service development
- **crawler-dev**: Crawler service development
- **test-runner**: Test execution and validation
- **integration-dev**: Cross-service integration work

---

## Phase 0: Configuration Models (MVP)

**Goal**: Create database-backed configuration for product types, field definitions, and quality gates

### 0.0 Codebase Analysis

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 0.0.1 **ANALYZE**: Review existing models.py structure and identify integration points for new config models | [ ] | Explore | None |
| 0.0.2 **ANALYZE**: Review existing DiscoveredProduct, WhiskeyDetails, PortWineDetails field definitions for schema mapping | [ ] | Explore | None |
| 0.0.3 **ANALYZE**: Review existing admin.py patterns for Django Admin implementation | [ ] | Explore | None |

**Analysis Tasks Output:**
- Document existing model organization (single file vs module)
- Map all fields from DiscoveredProduct, WhiskeyDetails, PortWineDetails for FieldDefinition seed data
- Document admin.py patterns (inlines, filters, list displays)
- Identify any existing configuration patterns in codebase

---

### 0.1 Core Configuration Models

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 0.1.1 Write unit tests for `ProductTypeConfig` model | [ ] | crawler-dev | 0.0.1 |
| 0.1.2 Write unit tests for `FieldDefinition` model | [ ] | crawler-dev | None |
| 0.1.3 Write unit tests for `QualityGateConfig` model | [ ] | crawler-dev | None |
| 0.1.4 Write unit tests for `EnrichmentConfig` model | [ ] | crawler-dev | None |
| 0.1.5 Implement `ProductTypeConfig` model | [ ] | crawler-dev | 0.1.1 |
| 0.1.6 Implement `FieldDefinition` model with target_model/target_field mapping | [ ] | crawler-dev | 0.1.2 |
| 0.1.7 Implement `QualityGateConfig` model | [ ] | crawler-dev | 0.1.3 |
| 0.1.8 Implement `EnrichmentConfig` model | [ ] | crawler-dev | 0.1.4 |
| 0.1.9 Create database migrations | [ ] | crawler-dev | 0.1.5-0.1.8 |
| 0.1.10 Run migrations and verify tables created | [ ] | test-runner | 0.1.9 |

**Files to create:**
- `spiritswise-web-crawler/crawler/models/config.py` (or add to existing models.py)

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_config_models.py`

---

### 0.2 Django Admin Configuration

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 0.2.1 Implement `ProductTypeConfigAdmin` with inline FieldDefinitions | [ ] | crawler-dev | 0.1.10 |
| 0.2.2 Implement `FieldDefinitionAdmin` with filtering by product type | [ ] | crawler-dev | 0.1.10 |
| 0.2.3 Implement `QualityGateConfigAdmin` | [ ] | crawler-dev | 0.1.10 |
| 0.2.4 Implement `EnrichmentConfigAdmin` | [ ] | crawler-dev | 0.1.10 |
| 0.2.5 Verify admin UI works correctly | [ ] | test-runner | 0.2.1-0.2.4 |

**Files to modify:**
- `spiritswise-web-crawler/crawler/admin.py`

---

### 0.3 Schema Builder Service

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 0.3.1 Write unit tests for `build_extraction_schema()` method | [ ] | crawler-dev | 0.1.10 |
| 0.3.2 Write unit tests for loading base + type-specific fields | [ ] | crawler-dev | 0.1.10 |
| 0.3.3 Write unit tests for `to_extraction_schema()` conversion | [ ] | crawler-dev | 0.1.10 |
| 0.3.4 Implement `ConfigService` class | [ ] | crawler-dev | 0.3.1-0.3.3 |
| 0.3.5 Implement `build_extraction_schema()` method | [ ] | crawler-dev | 0.3.4 |
| 0.3.6 Implement caching for config lookups | [ ] | crawler-dev | 0.3.5 |
| 0.3.7 Run config service tests and verify all pass | [ ] | test-runner | 0.3.6 |

**Files to create:**
- `spiritswise-web-crawler/crawler/services/config_service.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_config_service.py`

---

### 0.4 Seed Initial Configuration Data

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 0.4.1 Create shared/base FieldDefinitions (name, brand, description, abv, etc.) | [ ] | crawler-dev | 0.1.10 |
| 0.4.2 Create whiskey ProductTypeConfig seed data | [ ] | crawler-dev | 0.1.10 |
| 0.4.3 Create whiskey FieldDefinitions (distillery, mash_bill, peated, cask_type, etc.) | [ ] | crawler-dev | 0.4.2 |
| 0.4.4 Create whiskey QualityGateConfig (ABV required for PARTIAL/COMPLETE) | [ ] | crawler-dev | 0.4.2 |
| 0.4.5 Create whiskey EnrichmentConfig templates | [ ] | crawler-dev | 0.4.2 |
| 0.4.6 Create port_wine ProductTypeConfig seed data | [ ] | crawler-dev | 0.1.10 |
| 0.4.7 Create port_wine FieldDefinitions (port_style, vintage, sweetness, etc.) | [ ] | crawler-dev | 0.4.6 |
| 0.4.8 Create port_wine QualityGateConfig (ABV required for PARTIAL/COMPLETE) | [ ] | crawler-dev | 0.4.6 |
| 0.4.9 Create port_wine EnrichmentConfig templates | [ ] | crawler-dev | 0.4.6 |
| 0.4.10 Implement `seed_config` management command | [ ] | crawler-dev | 0.4.1-0.4.9 |
| 0.4.11 Run seed command and verify whiskey config data | [ ] | test-runner | 0.4.10 |
| 0.4.12 Run seed command and verify port_wine config data | [ ] | test-runner | 0.4.10 |

**Full Field Schema Requirements:**

Each FieldDefinition must include:
- `field_name`, `display_name`, `field_group`
- `field_type` (string, integer, float, boolean, array, object)
- `description` - Clear description for AI extraction
- `examples` - JSON array of example values
- `target_model` - Django model (DiscoveredProduct, WhiskeyDetails, PortWineDetails, ProductAward, etc.)
- `target_field` - Field name in target model

**Files to create:**
- `spiritswise-web-crawler/crawler/management/commands/seed_config.py`
- `spiritswise-web-crawler/crawler/fixtures/base_fields.json` (~20 shared fields)
- `spiritswise-web-crawler/crawler/fixtures/whiskey_config.json` (~25 type-specific fields)
- `spiritswise-web-crawler/crawler/fixtures/port_wine_config.json` (~20 type-specific fields)

---

## Phase 1: AI Service V2 Endpoint

**Goal**: Create new `/api/v2/extract/` endpoint - content-agnostic, receives full schema in request

### 1.1 Request/Response Schemas

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 1.1.1 Write unit tests for `ExtractionRequest` schema | [ ] | ai-service-dev | None |
| 1.1.2 Write unit tests for `ExtractionResponse` schema | [ ] | ai-service-dev | None |
| 1.1.3 Write unit tests for `ProductType` enum validation | [ ] | ai-service-dev | None |
| 1.1.4 Write unit tests for `product_category` validation per type | [ ] | ai-service-dev | None |
| 1.1.5 Write unit tests for `extraction_schema` validation (flat field list) | [ ] | ai-service-dev | None |
| 1.1.6 Implement `SourceData` Pydantic model | [ ] | ai-service-dev | 1.1.1 |
| 1.1.7 Implement `extraction_schema` validator (validates field names) | [ ] | ai-service-dev | 1.1.5 |
| 1.1.8 Implement `ExtractionOptions` Pydantic model | [ ] | ai-service-dev | 1.1.1 |
| 1.1.9 Implement `ExtractionRequest` Pydantic model | [ ] | ai-service-dev | 1.1.6, 1.1.7, 1.1.8 |
| 1.1.10 Implement `ExtractedProduct` Pydantic model | [ ] | ai-service-dev | 1.1.2 |
| 1.1.11 Implement `ExtractionResponse` Pydantic model | [ ] | ai-service-dev | 1.1.10 |
| 1.1.12 Run schema tests and verify all pass | [ ] | test-runner | 1.1.11 |

**Files to create:**
- `spiritswise-ai-enhancement-service/ai_enhancement_engine/api/v2/__init__.py`
- `spiritswise-ai-enhancement-service/ai_enhancement_engine/api/v2/schemas.py`

**Test file:**
- `spiritswise-ai-enhancement-service/tests/unit/test_v2_schemas.py`

---

### 1.2 Extraction Prompt Builder

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 1.2.1 Write unit tests for `build_extraction_prompt()` | [ ] | ai-service-dev | None |
| 1.2.2 Write unit tests for `get_type_context()` whiskey | [ ] | ai-service-dev | None |
| 1.2.3 Write unit tests for `get_type_context()` port_wine | [ ] | ai-service-dev | None |
| 1.2.4 Write unit tests for `get_field_descriptions()` | [ ] | ai-service-dev | None |
| 1.2.5 Write unit tests for category-specific prompts | [ ] | ai-service-dev | None |
| 1.2.6 Implement `TYPE_CONTEXTS` configuration | [ ] | ai-service-dev | 1.2.2, 1.2.3 |
| 1.2.7 Implement `FIELD_DESCRIPTIONS` configuration | [ ] | ai-service-dev | 1.2.4 |
| 1.2.8 Implement `get_type_context()` function | [ ] | ai-service-dev | 1.2.6 |
| 1.2.9 Implement `get_field_descriptions()` function | [ ] | ai-service-dev | 1.2.7 |
| 1.2.10 Implement `build_extraction_prompt()` function | [ ] | ai-service-dev | 1.2.8, 1.2.9 |
| 1.2.11 Run prompt builder tests and verify all pass | [ ] | test-runner | 1.2.10 |

**Files to create:**
- `spiritswise-ai-enhancement-service/ai_enhancement_engine/prompts/v2_extraction_prompts.py`

**Test file:**
- `spiritswise-ai-enhancement-service/tests/unit/test_v2_prompts.py`

---

### 1.3 V2 Extractor Service

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 1.3.1 Write unit tests for single product extraction | [ ] | ai-service-dev | 1.1.11 |
| 1.3.2 Write unit tests for multi-product detection | [ ] | ai-service-dev | 1.1.11 |
| 1.3.3 Write unit tests for field confidence calculation | [ ] | ai-service-dev | 1.1.11 |
| 1.3.4 Write unit tests for extraction summary generation | [ ] | ai-service-dev | 1.1.11 |
| 1.3.5 Write unit tests for error handling (invalid content) | [ ] | ai-service-dev | 1.1.11 |
| 1.3.6 Write unit tests for product type validation | [ ] | ai-service-dev | 1.1.11 |
| 1.3.7 Implement `ExtractorV2Service` class skeleton | [ ] | ai-service-dev | 1.3.1-1.3.6 |
| 1.3.8 Implement `extract()` main method | [ ] | ai-service-dev | 1.3.7, 1.2.11 |
| 1.3.9 Implement `_call_llm()` OpenAI integration | [ ] | ai-service-dev | 1.3.8 |
| 1.3.10 Implement `_parse_llm_response()` JSON parsing | [ ] | ai-service-dev | 1.3.9 |
| 1.3.11 Implement `_calculate_confidences()` method | [ ] | ai-service-dev | 1.3.10 |
| 1.3.12 Implement `_build_extraction_summary()` method | [ ] | ai-service-dev | 1.3.11 |
| 1.3.13 Implement `_detect_multi_product()` method | [ ] | ai-service-dev | 1.3.12 |
| 1.3.14 Run extractor service tests and verify all pass | [ ] | test-runner | 1.3.13 |

**Files to create:**
- `spiritswise-ai-enhancement-service/ai_enhancement_engine/services/extractor_v2.py`

**Test file:**
- `spiritswise-ai-enhancement-service/tests/unit/test_extractor_v2.py`

---

### 1.4 V2 API Endpoint

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 1.4.1 Write integration tests for POST `/api/v2/extract/` | [ ] | ai-service-dev | 1.3.14 |
| 1.4.2 Write tests for request validation errors | [ ] | ai-service-dev | 1.1.11 |
| 1.4.3 Write tests for successful single product response | [ ] | ai-service-dev | 1.3.14 |
| 1.4.4 Write tests for successful multi-product response | [ ] | ai-service-dev | 1.3.14 |
| 1.4.5 Write tests for error responses | [ ] | ai-service-dev | 1.3.14 |
| 1.4.6 Implement `extract_v2()` view function | [ ] | ai-service-dev | 1.4.1-1.4.5 |
| 1.4.7 Add URL routing for `/api/v2/extract/` | [ ] | ai-service-dev | 1.4.6 |
| 1.4.8 Run API endpoint tests and verify all pass | [ ] | test-runner | 1.4.7 |

**Files to create:**
- `spiritswise-ai-enhancement-service/ai_enhancement_engine/api/v2/endpoints.py`

**Files to modify:**
- `spiritswise-ai-enhancement-service/ai_enhancement_engine/urls.py`

**Test file:**
- `spiritswise-ai-enhancement-service/tests/integration/test_v2_endpoint.py`

---

## Phase 2: Crawler Quality Gate

**Goal**: Implement crawler-side quality assessment that decides save/enrich decisions

### 2.1 Quality Thresholds Configuration

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 2.1.1 Write unit tests for `QualityThresholds` defaults | [ ] | crawler-dev | None |
| 2.1.2 Write unit tests for whiskey COMPLETE_FIELDS | [ ] | crawler-dev | None |
| 2.1.3 Write unit tests for port_wine COMPLETE_FIELDS | [ ] | crawler-dev | None |
| 2.1.4 Write unit tests for confidence thresholds | [ ] | crawler-dev | None |
| 2.1.5 Implement `QualityThresholds` dataclass | [ ] | crawler-dev | 2.1.1-2.1.4 |
| 2.1.6 Run threshold tests and verify all pass | [ ] | test-runner | 2.1.5 |

**Files to create:**
- `spiritswise-web-crawler/crawler/services/quality_gate.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_quality_gate.py`

---

### 2.2 Quality Assessment

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 2.2.1 Write unit tests for `QualityAssessment` dataclass | [ ] | crawler-dev | None |
| 2.2.2 Write unit tests for SKELETON status assessment | [ ] | crawler-dev | 2.1.6 |
| 2.2.3 Write unit tests for PARTIAL status assessment | [ ] | crawler-dev | 2.1.6 |
| 2.2.4 Write unit tests for COMPLETE status assessment | [ ] | crawler-dev | 2.1.6 |
| 2.2.5 Write unit tests for ENRICHED status assessment | [ ] | crawler-dev | 2.1.6 |
| 2.2.6 Write unit tests for rejection scenarios | [ ] | crawler-dev | 2.1.6 |
| 2.2.7 Write unit tests for enrichment priority calculation | [ ] | crawler-dev | 2.1.6 |
| 2.2.8 Implement `QualityAssessment` dataclass | [ ] | crawler-dev | 2.2.1 |
| 2.2.9 Implement `ProductStatus` enum | [ ] | crawler-dev | 2.2.1 |
| 2.2.10 Run assessment tests and verify all pass | [ ] | test-runner | 2.2.9 |

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_quality_gate.py` (extend)

---

### 2.3 Quality Gate Class

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 2.3.1 Write unit tests for `QualityGate.assess()` whiskey | [ ] | crawler-dev | 2.2.10 |
| 2.3.2 Write unit tests for `QualityGate.assess()` port_wine | [ ] | crawler-dev | 2.2.10 |
| 2.3.3 Write unit tests for confidence-based filtering | [ ] | crawler-dev | 2.2.10 |
| 2.3.4 Write unit tests for completeness score calculation | [ ] | crawler-dev | 2.2.10 |
| 2.3.5 Write unit tests for missing fields identification | [ ] | crawler-dev | 2.2.10 |
| 2.3.6 Implement `QualityGate` class skeleton | [ ] | crawler-dev | 2.3.1-2.3.5 |
| 2.3.7 Implement `assess()` method | [ ] | crawler-dev | 2.3.6 |
| 2.3.8 Implement `_calculate_completeness()` method | [ ] | crawler-dev | 2.3.7 |
| 2.3.9 Implement `_determine_status()` method | [ ] | crawler-dev | 2.3.8 |
| 2.3.10 Implement `_calculate_enrichment_priority()` method | [ ] | crawler-dev | 2.3.9 |
| 2.3.11 Run quality gate tests and verify all pass | [ ] | test-runner | 2.3.10 |

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_quality_gate.py` (extend)

---

## Phase 2.5: Content Preprocessing

**Goal**: Implement content preprocessing to reduce AI token costs by ~93%

### 2.5.1 Content Preprocessor Core

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 2.5.1.1 Write unit tests for `_extract_clean_text()` method | [ ] | crawler-dev | None |
| 2.5.1.2 Write unit tests for `_clean_structured_html()` method | [ ] | crawler-dev | None |
| 2.5.1.3 Write unit tests for `_extract_headings()` helper | [ ] | crawler-dev | None |
| 2.5.1.4 Write unit tests for `_basic_text_extract()` fallback | [ ] | crawler-dev | None |
| 2.5.1.5 Write unit tests for content type detection | [ ] | crawler-dev | None |
| 2.5.1.6 Implement `ContentPreprocessor` class skeleton | [ ] | crawler-dev | 2.5.1.1-2.5.1.5 |
| 2.5.1.7 Implement `_extract_headings()` method | [ ] | crawler-dev | 2.5.1.6 |
| 2.5.1.8 Implement `_basic_text_extract()` fallback | [ ] | crawler-dev | 2.5.1.7 |
| 2.5.1.9 Implement `_extract_clean_text()` with trafilatura | [ ] | crawler-dev | 2.5.1.8 |
| 2.5.1.10 Implement `_clean_structured_html()` for list pages | [ ] | crawler-dev | 2.5.1.9 |
| 2.5.1.11 Implement `preprocess()` main method | [ ] | crawler-dev | 2.5.1.10 |
| 2.5.1.12 Run preprocessor tests and verify all pass | [ ] | test-runner | 2.5.1.11 |

**Files to create:**
- `spiritswise-web-crawler/crawler/services/content_preprocessor.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_content_preprocessor.py`

---

### 2.5.2 Content Type Handling

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 2.5.2.1 Write unit tests for `cleaned_text` content type | [ ] | crawler-dev | 2.5.1.12 |
| 2.5.2.2 Write unit tests for `structured_html` content type | [ ] | crawler-dev | 2.5.1.12 |
| 2.5.2.3 Write unit tests for `raw_html` fallback | [ ] | crawler-dev | 2.5.1.12 |
| 2.5.2.4 Write unit tests for token estimation | [ ] | crawler-dev | None |
| 2.5.2.5 Write unit tests for oversized content handling | [ ] | crawler-dev | 2.5.1.12 |
| 2.5.2.6 Implement `estimate_tokens()` method | [ ] | crawler-dev | 2.5.2.4 |
| 2.5.2.7 Implement `_should_preserve_structure()` detector | [ ] | crawler-dev | 2.5.2.1-2.5.2.3 |
| 2.5.2.8 Implement oversized content truncation | [ ] | crawler-dev | 2.5.2.5, 2.5.2.6 |
| 2.5.2.9 Run content type tests and verify all pass | [ ] | test-runner | 2.5.2.8 |

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_content_preprocessor.py` (extend)

---

## Phase 3: V2 API Client

**Goal**: Create crawler client for AI Service V2 endpoint with integrated content preprocessing

### 3.1 V2 Client Implementation

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 3.1.1 Write unit tests for request building | [ ] | crawler-dev | 1.1.11, 2.5.2.9 |
| 3.1.2 Write unit tests for response parsing | [ ] | crawler-dev | 1.1.11 |
| 3.1.3 Write unit tests for error handling | [ ] | crawler-dev | 1.1.11 |
| 3.1.4 Write unit tests for retry logic | [ ] | crawler-dev | None |
| 3.1.5 Write unit tests for timeout handling | [ ] | crawler-dev | None |
| 3.1.6 Write unit tests for content preprocessing integration | [ ] | crawler-dev | 2.5.2.9 |
| 3.1.7 Implement `AIClientV2` class skeleton | [ ] | crawler-dev | 3.1.1-3.1.6 |
| 3.1.8 Implement `extract()` async method | [ ] | crawler-dev | 3.1.7 |
| 3.1.9 Implement `_build_request()` method with preprocessing | [ ] | crawler-dev | 3.1.8, 2.5.2.9 |
| 3.1.10 Implement `_parse_response()` method | [ ] | crawler-dev | 3.1.9 |
| 3.1.11 Implement retry with exponential backoff | [ ] | crawler-dev | 3.1.10 |
| 3.1.12 Run client tests and verify all pass | [ ] | test-runner | 3.1.11 |

**Files to create:**
- `spiritswise-web-crawler/crawler/services/ai_client_v2.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_ai_client_v2.py`

---

## Phase 4: Enrichment Orchestrator

**Goal**: Implement progressive multi-source enrichment

### 4.1 Enrichment Result and Configuration

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 4.1.1 Write unit tests for `EnrichmentResult` dataclass | [ ] | crawler-dev | None |
| 4.1.2 Write unit tests for enrichment limits | [ ] | crawler-dev | None |
| 4.1.3 Implement `EnrichmentResult` dataclass | [ ] | crawler-dev | 4.1.1 |
| 4.1.4 Implement `EnrichmentConfig` dataclass | [ ] | crawler-dev | 4.1.2 |
| 4.1.5 Run config tests and verify all pass | [ ] | test-runner | 4.1.4 |

**Files to create:**
- `spiritswise-web-crawler/crawler/services/enrichment_orchestrator.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_enrichment_orchestrator.py`

---

### 4.2 Search Query Building

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 4.2.1 Write unit tests for tasting notes search query | [ ] | crawler-dev | None |
| 4.2.2 Write unit tests for ABV search query | [ ] | crawler-dev | None |
| 4.2.3 Write unit tests for production info search query | [ ] | crawler-dev | None |
| 4.2.4 Write unit tests for generic fallback query | [ ] | crawler-dev | None |
| 4.2.5 Implement `_build_search_query()` method | [ ] | crawler-dev | 4.2.1-4.2.4 |
| 4.2.6 Run search query tests and verify all pass | [ ] | test-runner | 4.2.5 |

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_enrichment_orchestrator.py` (extend)

---

### 4.3 Data Merging

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 4.3.1 Write unit tests for empty field merge | [ ] | crawler-dev | None |
| 4.3.2 Write unit tests for higher confidence replace | [ ] | crawler-dev | None |
| 4.3.3 Write unit tests for lower confidence keep | [ ] | crawler-dev | None |
| 4.3.4 Write unit tests for conflicting values | [ ] | crawler-dev | None |
| 4.3.5 Implement `_merge_data()` method | [ ] | crawler-dev | 4.3.1-4.3.4 |
| 4.3.6 Run merge tests and verify all pass | [ ] | test-runner | 4.3.5 |

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_enrichment_orchestrator.py` (extend)

---

### 4.4 Enrichment Loop

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 4.4.1 Write unit tests for single source enrichment | [ ] | crawler-dev | 4.1.5, 4.2.6, 4.3.6 |
| 4.4.2 Write unit tests for multi-source enrichment | [ ] | crawler-dev | 4.4.1 |
| 4.4.3 Write unit tests for limit enforcement | [ ] | crawler-dev | 4.4.1 |
| 4.4.4 Write unit tests for COMPLETE status stop | [ ] | crawler-dev | 4.4.1, 2.3.11 |
| 4.4.5 Write unit tests for timeout handling | [ ] | crawler-dev | 4.4.1 |
| 4.4.6 Implement `EnrichmentOrchestrator` class skeleton | [ ] | crawler-dev | 4.4.1-4.4.5 |
| 4.4.7 Implement `enrich_product()` async method | [ ] | crawler-dev | 4.4.6 |
| 4.4.8 Implement `_search_sources()` method | [ ] | crawler-dev | 4.4.7 |
| 4.4.9 Implement `_extract_from_source()` method | [ ] | crawler-dev | 4.4.8, 3.1.11 |
| 4.4.10 Implement `_check_limits()` method | [ ] | crawler-dev | 4.4.9 |
| 4.4.11 Run enrichment loop tests and verify all pass | [ ] | test-runner | 4.4.10 |

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_enrichment_orchestrator.py` (extend)

---

### 4.5 Source Tracking and Content Archival

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 4.5.0 **ANALYZE**: Review existing CrawledSource, ProductSource, ProductFieldSource models and document current state vs required changes | [ ] | Explore | None |
| 4.5.1 Write unit tests for `preprocessed_content` field migration | [ ] | crawler-dev | 4.5.0 |
| 4.5.2 Write unit tests for `cleanup_eligible` field logic | [ ] | crawler-dev | 4.5.0 |
| 4.5.3 Add `preprocessed_content`, `preprocessed_at` fields to CrawledSource | [ ] | crawler-dev | 4.5.1 |
| 4.5.4 Add `cleanup_eligible` field to CrawledSource | [ ] | crawler-dev | 4.5.2 |
| 4.5.5 Create database migration for new fields | [ ] | crawler-dev | 4.5.3, 4.5.4 |
| 4.5.6 Run migration and verify fields exist | [ ] | test-runner | 4.5.5 |
| 4.5.7 Write unit tests for storing preprocessed content | [ ] | crawler-dev | 4.5.6 |
| 4.5.8 Write unit tests for ProductSource linkage | [ ] | crawler-dev | 4.5.6 |
| 4.5.9 Write unit tests for ProductFieldSource provenance | [ ] | crawler-dev | 4.5.6 |
| 4.5.10 Implement `store_crawled_source()` method | [ ] | crawler-dev | 4.5.7-4.5.9 |
| 4.5.11 Implement `link_product_to_source()` method | [ ] | crawler-dev | 4.5.10 |
| 4.5.12 Implement `track_field_provenance()` method | [ ] | crawler-dev | 4.5.11 |
| 4.5.13 Run source tracking tests and verify all pass | [ ] | test-runner | 4.5.12 |

**Analysis Task 4.5.0 Output:**
- Document existing fields in CrawledSource model
- Document existing ProductSource and ProductFieldSource models
- List fields to add vs fields already present
- Identify any existing methods that need modification
- Note any conflicts with existing code

**Files to modify:**
- `spiritswise-web-crawler/crawler/models.py` (add fields to CrawledSource)
- `spiritswise-web-crawler/crawler/services/source_tracker.py` (new)

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_source_tracker.py`

---

### 4.6 Internet Archive (Wayback Machine) Integration

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 4.6.0 **ANALYZE**: Review existing wayback_url, wayback_status fields in CrawledSource and document Wayback API requirements | [ ] | Explore | 4.5.0 |
| 4.6.1 Write unit tests for Wayback save request | [ ] | crawler-dev | 4.6.0 |
| 4.6.2 Write unit tests for archive URL extraction | [ ] | crawler-dev | 4.6.0 |
| 4.6.3 Write unit tests for retry on failure | [ ] | crawler-dev | 4.6.0 |
| 4.6.4 Write unit tests for cleanup eligibility check | [ ] | crawler-dev | 4.5.6 |
| 4.6.5 Implement `WaybackService` class skeleton | [ ] | crawler-dev | 4.6.1-4.6.4 |
| 4.6.6 Implement `archive_url()` async method | [ ] | crawler-dev | 4.6.5 |
| 4.6.7 Implement `_extract_archive_url()` method | [ ] | crawler-dev | 4.6.6 |
| 4.6.8 Implement `check_cleanup_eligible()` method | [ ] | crawler-dev | 4.6.7 |
| 4.6.9 Run Wayback service tests and verify all pass | [ ] | test-runner | 4.6.8 |

**Analysis Task 4.6.0 Output:**
- Document existing wayback_url, wayback_saved_at, wayback_status fields
- Research Wayback Machine Save API (https://web.archive.org/save/)
- Document rate limits and best practices
- Identify async/celery integration pattern

**Files to create:**
- `spiritswise-web-crawler/crawler/services/wayback_service.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_wayback_service.py`

---

### 4.7 Content Cleanup Job

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 4.7.0 **ANALYZE**: Review existing raw_content_cleared field and Celery beat schedule patterns in codebase | [ ] | Explore | 4.5.0 |
| 4.7.1 Write unit tests for cleanup eligibility query | [ ] | crawler-dev | 4.7.0, 4.5.6, 4.6.9 |
| 4.7.2 Write unit tests for raw_content clearing | [ ] | crawler-dev | 4.7.0, 4.5.6 |
| 4.7.3 Write unit tests for batch cleanup processing | [ ] | crawler-dev | 4.7.1 |
| 4.7.4 Implement `cleanup_raw_content` management command | [ ] | crawler-dev | 4.7.1-4.7.3 |
| 4.7.5 Add cleanup job to Celery beat schedule | [ ] | crawler-dev | 4.7.4 |
| 4.7.6 Run cleanup tests and verify all pass | [ ] | test-runner | 4.7.5 |

**Analysis Task 4.7.0 Output:**
- Document existing raw_content_cleared usage
- Review existing Celery beat schedule configuration
- Identify batch processing patterns in codebase

**Files to create:**
- `spiritswise-web-crawler/crawler/management/commands/cleanup_raw_content.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_cleanup_command.py`

---

### 4.8 Wayback Archive Job

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 4.8.0 **ANALYZE**: Review existing management commands and rate limiting patterns for external API calls | [ ] | Explore | 4.6.0 |
| 4.8.1 Write unit tests for pending archive query | [ ] | crawler-dev | 4.8.0, 4.6.9 |
| 4.8.2 Write unit tests for rate limiting | [ ] | crawler-dev | 4.8.0 |
| 4.8.3 Write unit tests for batch archive processing | [ ] | crawler-dev | 4.8.1 |
| 4.8.4 Implement `archive_to_wayback` management command | [ ] | crawler-dev | 4.8.1-4.8.3 |
| 4.8.5 Add archive job to Celery beat schedule | [ ] | crawler-dev | 4.8.4 |
| 4.8.6 Run archive job tests and verify all pass | [ ] | test-runner | 4.8.5 |

**Analysis Task 4.8.0 Output:**
- Review existing management command patterns
- Document rate limiting approaches for SerpAPI and other external calls
- Identify retry/backoff patterns in codebase

**Files to create:**
- `spiritswise-web-crawler/crawler/management/commands/archive_to_wayback.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/unit/test_wayback_command.py`

---

## Phase 5: Discovery Orchestrator Integration

**Goal**: Update DiscoveryOrchestrator to use V2 API and QualityGate

### 5.1 Single Product Flow Update

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 5.1.1 Write integration tests for V2 single product flow | [ ] | crawler-dev | 3.1.11, 2.3.11 |
| 5.1.2 Write tests for quality gate integration | [ ] | crawler-dev | 5.1.1 |
| 5.1.3 Write tests for enrichment queue decision | [ ] | crawler-dev | 5.1.1, 4.4.11 |
| 5.1.4 Update `_extract_and_save_product()` to use V2 | [ ] | crawler-dev | 5.1.1-5.1.3 |
| 5.1.5 Integrate `QualityGate.assess()` in save flow | [ ] | crawler-dev | 5.1.4 |
| 5.1.6 Add enrichment queue logic | [ ] | crawler-dev | 5.1.5 |
| 5.1.7 Run single product flow tests and verify all pass | [ ] | test-runner | 5.1.6 |

**Files to modify:**
- `spiritswise-web-crawler/crawler/services/discovery_orchestrator.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/integration/test_discovery_v2.py`

---

### 5.2 List Page Flow Update

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 5.2.1 Write integration tests for V2 list page flow | [ ] | crawler-dev | 3.1.11, 2.3.11 |
| 5.2.2 Write tests for multi-product response handling | [ ] | crawler-dev | 5.2.1 |
| 5.2.3 Write tests for skeleton product creation | [ ] | crawler-dev | 5.2.1 |
| 5.2.4 Write tests for detail_url follow-up | [ ] | crawler-dev | 5.2.1 |
| 5.2.5 Update `_extract_list_products()` to use V2 | [ ] | crawler-dev | 5.2.1-5.2.4 |
| 5.2.6 Update `_enrich_product_from_list()` to use V2 | [ ] | crawler-dev | 5.2.5 |
| 5.2.7 Integrate enrichment orchestrator for skeletons | [ ] | crawler-dev | 5.2.6, 4.4.11 |
| 5.2.8 Run list page flow tests and verify all pass | [ ] | test-runner | 5.2.7 |

**Test file:**
- `spiritswise-web-crawler/crawler/tests/integration/test_discovery_v2.py` (extend)

---

## Phase 6: End-to-End Testing

**Goal**: Validate complete flow from URL to saved product

### 6.1 Whiskey E2E Tests

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 6.1.1 Write E2E test for single whiskey product page | [ ] | integration-dev | 5.1.7 |
| 6.1.2 Write E2E test for whiskey list page (best of) | [ ] | integration-dev | 5.2.8 |
| 6.1.3 Write E2E test for whiskey awards page (IWSC) | [ ] | integration-dev | 5.2.8 |
| 6.1.4 Write E2E test for whiskey enrichment flow | [ ] | integration-dev | 5.1.7, 4.4.11 |
| 6.1.5 Write E2E test for bourbon category extraction | [ ] | integration-dev | 5.1.7 |
| 6.1.6 Write E2E test for scotch category extraction | [ ] | integration-dev | 5.1.7 |
| 6.1.7 Run whiskey E2E tests and verify all pass | [ ] | test-runner | 6.1.1-6.1.6 |

**Test file:**
- `spiritswise-web-crawler/tests/e2e/test_whiskey_v2_flow.py`

---

### 6.2 Port Wine E2E Tests

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 6.2.1 Write E2E test for single port wine product page | [ ] | integration-dev | 5.1.7 |
| 6.2.2 Write E2E test for port wine list page | [ ] | integration-dev | 5.2.8 |
| 6.2.3 Write E2E test for tawny category extraction | [ ] | integration-dev | 5.1.7 |
| 6.2.4 Write E2E test for vintage category extraction | [ ] | integration-dev | 5.1.7 |
| 6.2.5 Write E2E test for port wine enrichment flow | [ ] | integration-dev | 5.1.7, 4.4.11 |
| 6.2.6 Run port wine E2E tests and verify all pass | [ ] | test-runner | 6.2.1-6.2.5 |

**Test file:**
- `spiritswise-web-crawler/tests/e2e/test_port_wine_v2_flow.py`

---

### 6.3 Cross-Service Integration Tests

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 6.3.1 Write integration test for Crawler → AI Service V2 | [ ] | integration-dev | 1.4.8, 3.1.11 |
| 6.3.2 Write integration test for error propagation | [ ] | integration-dev | 6.3.1 |
| 6.3.3 Write integration test for timeout handling | [ ] | integration-dev | 6.3.1 |
| 6.3.4 Write integration test for rate limiting | [ ] | integration-dev | 6.3.1 |
| 6.3.5 Run cross-service tests and verify all pass | [ ] | test-runner | 6.3.1-6.3.4 |

**Test file:**
- `spiritswise-web-crawler/tests/integration/test_crawler_ai_service_v2.py`

---

## Phase 7: Competition Flow Update

**Goal**: Update CompetitionOrchestrator to use V2 architecture

### 7.1 Competition Orchestrator Update

| Task | Status | Subagent | Dependencies |
|------|--------|----------|--------------|
| 7.1.1 Write tests for IWSC extraction with V2 | [ ] | crawler-dev | 5.2.8 |
| 7.1.2 Write tests for SFWSC extraction with V2 | [ ] | crawler-dev | 5.2.8 |
| 7.1.3 Write tests for award data extraction | [ ] | crawler-dev | 5.2.8 |
| 7.1.4 Update `CompetitionOrchestrator` to use AIClientV2 | [ ] | crawler-dev | 7.1.1-7.1.3 |
| 7.1.5 Integrate QualityGate for competition products | [ ] | crawler-dev | 7.1.4 |
| 7.1.6 Run competition flow tests and verify all pass | [ ] | test-runner | 7.1.5 |

**Files to modify:**
- `spiritswise-web-crawler/crawler/services/competition_orchestrator.py`

**Test file:**
- `spiritswise-web-crawler/crawler/tests/integration/test_competition_v2.py`

---

## Summary

### Total Tasks by Phase

| Phase | Tasks | Tests | Implementation | Analysis |
|-------|-------|-------|----------------|----------|
| Phase 0: Configuration Models | 37 | 7 | 27 | 3 |
| Phase 1: AI Service V2 | 41 | 18 | 23 | 0 |
| Phase 2: Quality Gate | 26 | 14 | 12 | 0 |
| Phase 2.5: Content Preprocessing | 21 | 10 | 11 | 0 |
| Phase 3: V2 Client | 12 | 6 | 6 | 0 |
| Phase 4: Enrichment + Source Tracking | 65 | 32 | 29 | 4 |
| Phase 5: Discovery Integration | 15 | 7 | 8 | 0 |
| Phase 6: E2E Tests | 18 | 18 | 0 | 0 |
| Phase 7: Competition | 6 | 3 | 3 | 0 |
| **TOTAL** | **241** | **115** | **119** | **7** |

### Execution Order

**IMPORTANT**: Each phase with ANALYZE tasks (marked with 0.0.x, 4.5.0, etc.) must complete analysis before implementation begins.

1. **Phase 0** (Configuration Models) - Start with 0.0.x analysis tasks, then implementation
2. **Phase 1** (AI Service) - Can start immediately (parallel with Phase 0)
3. **Phase 2** (Quality Gate) - Requires Phase 0 complete (uses QualityGateConfig)
4. **Phase 2.5** (Content Preprocessing) - Can start immediately (parallel with Phase 0 & 1)
5. **Phase 3** (V2 Client) - Requires Phases 0, 1, and 2.5 complete
6. **Phase 4** (Enrichment + Source Tracking + Wayback) - Start with 4.5.0-4.8.0 analysis tasks, then implementation
7. **Phase 5** (Discovery) - Requires Phases 3 and 4 complete
8. **Phase 6** (E2E) - Requires Phase 5 complete
9. **Phase 7** (Competition) - Requires Phase 5 complete

### Parallel Execution Opportunities

- Phase 0, Phase 1, and Phase 2.5 can run in parallel
- Phase 2 and Phase 4 depend on Phase 0 (Configuration Models)
- Phase 3 depends on Phase 0, 1, and 2.5
- Phase 6 and Phase 7 can run in parallel

---

## Notes

### For Subagents

1. **Always read the spec first**: `specs/CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md`
2. **Write tests BEFORE implementation** - TDD is mandatory
3. **Update this file** with status changes after each task
4. **Run tests** after each implementation task
5. **Document** any blockers or issues encountered

### Test File Naming Convention

- Unit tests: `tests/unit/test_<module>.py`
- Integration tests: `tests/integration/test_<feature>.py`
- E2E tests: `tests/e2e/test_<flow>.py`

### Status Update Format

When updating task status, use format:
```
| Task | [X] | subagent | Dependencies |
```

Add completion date in notes if needed:
```
| 1.1.1 Write unit tests for ExtractionRequest | [X] 2026-01-10 | ai-service-dev | None |
```
