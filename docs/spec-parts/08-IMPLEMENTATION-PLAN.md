# Section 8: Implementation Plan

> **Source:** Extracted from `FLOW_COMPARISON_ANALYSIS.md` lines 1559-2249

---

## 8. Implementation Plan

### 8.1 Core Data Structures

**ProductCandidate - Unified Intermediate Format:**
```python
# crawler/discovery/product_candidate.py

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal
from enum import Enum


class ExtractionSource(str, Enum):
    """How the product was initially extracted."""
    COMPETITION_PARSER = "competition_parser"  # BeautifulSoup from award site
    AI_LIST_EXTRACTION = "ai_list_extraction"  # LLM from list page
    AI_SINGLE_EXTRACTION = "ai_single_extraction"  # LLM from product page
    MANUAL = "manual"  # User-provided data


@dataclass
class ProductCandidate:
    """
    Unified intermediate format for all product discovery flows.

    This is the single data structure that ALL extractors produce,
    regardless of source type.
    """

    # === IDENTIFICATION ===
    name: str
    brand: Optional[str] = None

    # === SOURCE INFO ===
    extraction_source: ExtractionSource = ExtractionSource.AI_SINGLE_EXTRACTION
    source_url: str = ""
    direct_product_link: Optional[str] = None  # If we have a link to crawl

    # === PRODUCT DATA ===
    product_type: str = "whiskey"
    extracted_data: Dict[str, Any] = field(default_factory=dict)

    # === STRUCTURED DATA (extracted from extracted_data for convenience) ===
    abv: Optional[float] = None
    age_statement: Optional[str] = None
    volume_ml: Optional[int] = None
    description: Optional[str] = None

    # === TASTING PROFILE ===
    tasting_notes: Optional[str] = None
    nose_description: Optional[str] = None
    palate_flavors: Optional[List[str]] = None
    finish_description: Optional[str] = None

    # === RELATED DATA ===
    awards: List[Dict[str, Any]] = field(default_factory=list)
    ratings: List[Dict[str, Any]] = field(default_factory=list)
    images: List[Dict[str, Any]] = field(default_factory=list)
    prices: List[Dict[str, Any]] = field(default_factory=list)

    # === QUALITY INDICATORS ===
    extraction_confidence: float = 0.5
    field_confidences: Dict[str, float] = field(default_factory=dict)

    # === COMPUTED PROPERTIES ===
    @property
    def has_tasting_notes(self) -> bool:
        return bool(
            self.tasting_notes or
            self.nose_description or
            self.palate_flavors or
            self.finish_description
        )

    @property
    def has_pricing(self) -> bool:
        return len(self.prices) > 0

    @property
    def has_images(self) -> bool:
        return len(self.images) > 0

    @property
    def has_ratings(self) -> bool:
        return len(self.ratings) > 0

    @property
    def has_awards(self) -> bool:
        return len(self.awards) > 0

    @property
    def completeness_score(self) -> int:
        """Calculate how complete this candidate's data is."""
        score = 0

        # Required (40 points)
        if self.name: score += 20
        if self.brand: score += 10
        if self.product_type: score += 10

        # Important (30 points)
        if self.has_tasting_notes: score += 15
        if self.description: score += 10
        if self.abv: score += 5

        # Nice to have (30 points)
        if self.has_pricing: score += 10
        if self.has_images: score += 10
        if self.has_ratings: score += 5
        if self.has_awards: score += 5

        return min(score, 100)

    def needs_enrichment(self, threshold: int = 50) -> bool:
        """Check if this candidate needs additional enrichment."""
        return self.completeness_score < threshold

    def get_missing_data_types(self) -> List[str]:
        """Return list of data types that are missing."""
        missing = []
        if not self.has_tasting_notes:
            missing.append("tasting_notes")
        if not self.has_pricing:
            missing.append("pricing")
        if not self.has_images:
            missing.append("images")
        if not self.description:
            missing.append("description")
        return missing

    def to_extracted_data(self) -> Dict[str, Any]:
        """Convert to format expected by save_discovered_product."""
        data = {
            "name": self.name,
            "brand": self.brand,
            "product_type": self.product_type,
            "abv": self.abv,
            "age_statement": self.age_statement,
            "volume_ml": self.volume_ml,
            "description": self.description,
            "tasting_notes": self.tasting_notes,
            "nose_description": self.nose_description,
            "palate_flavors": self.palate_flavors,
            "finish_description": self.finish_description,
            **self.extracted_data,
        }

        if self.awards:
            data["awards"] = self.awards
        if self.ratings:
            data["ratings"] = self.ratings
        if self.images:
            data["images"] = self.images

        return {k: v for k, v in data.items() if v is not None}

    @classmethod
    def from_competition_result(cls, result: Dict[str, Any]) -> "ProductCandidate":
        """Create ProductCandidate from competition parser output."""
        return cls(
            name=result.get("product_name", ""),
            brand=result.get("producer"),
            extraction_source=ExtractionSource.COMPETITION_PARSER,
            product_type=cls._infer_product_type(result),
            awards=[{
                "competition": result.get("competition"),
                "year": result.get("year"),
                "medal": result.get("medal"),
                "category": result.get("category"),
            }],
            extraction_confidence=0.85,  # High for structured data
        )

    @classmethod
    def from_ai_extraction(cls, data: Dict[str, Any], source_url: str) -> "ProductCandidate":
        """Create ProductCandidate from AI extraction output."""
        return cls(
            name=data.get("name", ""),
            brand=data.get("brand"),
            extraction_source=ExtractionSource.AI_SINGLE_EXTRACTION,
            source_url=source_url,
            product_type=data.get("product_type", "whiskey"),
            extracted_data=data,
            abv=data.get("abv"),
            age_statement=data.get("age_statement"),
            description=data.get("description"),
            tasting_notes=data.get("tasting_notes"),
            nose_description=data.get("nose_description"),
            palate_flavors=data.get("palate_flavors"),
            awards=data.get("awards", []),
            ratings=data.get("ratings", []),
            images=data.get("images", []),
            extraction_confidence=data.get("confidence", 0.7),
        )

    @staticmethod
    def _infer_product_type(data: Dict[str, Any]) -> str:
        """Infer product type from data."""
        category = (data.get("category") or "").lower()
        if any(k in category for k in ["whisky", "whiskey", "bourbon", "scotch"]):
            return "whiskey"
        if any(k in category for k in ["port", "porto"]):
            return "port_wine"
        return "whiskey"
```

### 8.2 Unified Processing Pipeline

```python
# crawler/services/product_pipeline.py

import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

from crawler.models import DiscoveredProduct
from crawler.discovery.product_candidate import ProductCandidate, ExtractionSource
from crawler.services.product_saver import save_discovered_product, ProductSaveResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result of processing a ProductCandidate through the pipeline."""
    product: Optional[DiscoveredProduct]
    created: bool
    was_duplicate: bool
    was_enriched: bool
    enrichment_source: Optional[str]
    completeness_before: int
    completeness_after: int
    error: Optional[str] = None


class ProductPipeline:
    """
    Unified processing pipeline for all product discovery flows.

    Takes a ProductCandidate and:
    1. Checks for duplicates
    2. Evaluates completeness
    3. Enriches if needed and possible
    4. Saves the product
    """

    # Completeness threshold below which we attempt enrichment
    ENRICHMENT_THRESHOLD = 50

    # Minimum completeness to save a product
    MINIMUM_COMPLETENESS = 20

    def __init__(
        self,
        smart_crawler=None,
        serpapi_client=None,
        ai_client=None,
        enable_enrichment: bool = True,
    ):
        self.smart_crawler = smart_crawler
        self.serpapi_client = serpapi_client
        self.ai_client = ai_client
        self.enable_enrichment = enable_enrichment

    async def process(
        self,
        candidate: ProductCandidate,
        force_enrichment: bool = False,
        skip_enrichment: bool = False,
    ) -> PipelineResult:
        """
        Process a ProductCandidate through the full pipeline.

        Args:
            candidate: The product candidate to process
            force_enrichment: Force enrichment even if completeness is high
            skip_enrichment: Skip enrichment entirely

        Returns:
            PipelineResult with the created/updated product
        """
        result = PipelineResult(
            product=None,
            created=False,
            was_duplicate=False,
            was_enriched=False,
            enrichment_source=None,
            completeness_before=candidate.completeness_score,
            completeness_after=candidate.completeness_score,
        )

        # Validate minimum data
        if not candidate.name:
            result.error = "Product name is required"
            return result

        # Step 1: Check for duplicate
        existing = await self._find_duplicate(candidate)
        if existing:
            result.was_duplicate = True
            result.product = await self._merge_into_existing(existing, candidate)
            result.completeness_after = self._get_product_completeness(result.product)
            return result

        # Step 2: Evaluate completeness and enrich if needed
        if (
            self.enable_enrichment and
            not skip_enrichment and
            (force_enrichment or candidate.needs_enrichment(self.ENRICHMENT_THRESHOLD))
        ):
            enriched_candidate, enrichment_source = await self._enrich(candidate)
            if enriched_candidate:
                candidate = enriched_candidate
                result.was_enriched = True
                result.enrichment_source = enrichment_source

        # Step 3: Save the product
        if candidate.completeness_score < self.MINIMUM_COMPLETENESS:
            result.error = f"Completeness {candidate.completeness_score} below minimum {self.MINIMUM_COMPLETENESS}"
            return result

        save_result = await self._save(candidate)
        result.product = save_result.product
        result.created = save_result.created
        result.completeness_after = candidate.completeness_score

        return result

    async def process_batch(
        self,
        candidates: List[ProductCandidate],
        **kwargs,
    ) -> List[PipelineResult]:
        """Process multiple candidates."""
        results = []
        for candidate in candidates:
            result = await self.process(candidate, **kwargs)
            results.append(result)
        return results

    async def _find_duplicate(
        self,
        candidate: ProductCandidate,
    ) -> Optional[DiscoveredProduct]:
        """Find existing product that matches this candidate."""
        from asgiref.sync import sync_to_async
        from django.db.models import Q

        # Compute fingerprint
        fingerprint = DiscoveredProduct.compute_fingerprint({
            "name": candidate.name,
            "brand": candidate.brand,
            "product_type": candidate.product_type,
        })

        @sync_to_async
        def find():
            return DiscoveredProduct.objects.filter(
                Q(fingerprint=fingerprint) |
                Q(name__iexact=candidate.name)
            ).first()

        return await find()

    async def _merge_into_existing(
        self,
        existing: DiscoveredProduct,
        candidate: ProductCandidate,
    ) -> DiscoveredProduct:
        """Merge candidate data into existing product."""
        from asgiref.sync import sync_to_async
        from crawler.services.product_saver import create_product_awards

        @sync_to_async
        def merge():
            # Add new awards
            if candidate.awards:
                create_product_awards(existing, candidate.awards)

            # Merge any additional data that existing doesn't have
            # (Field-level merge logic)

            # Track that this product was also found via this source
            if existing.discovery_sources is None:
                existing.discovery_sources = []
            source_name = candidate.extraction_source.value
            if source_name not in existing.discovery_sources:
                existing.discovery_sources.append(source_name)
                existing.save(update_fields=["discovery_sources"])

            return existing

        return await merge()

    async def _enrich(
        self,
        candidate: ProductCandidate,
    ) -> tuple[Optional[ProductCandidate], Optional[str]]:
        """
        Attempt to enrich the candidate with additional data.

        Returns:
            Tuple of (enriched_candidate or None, enrichment_source or None)
        """
        # Strategy 1: If we have a direct product link, crawl it
        if candidate.direct_product_link and self.smart_crawler:
            enriched = await self._enrich_from_link(candidate)
            if enriched:
                return enriched, "direct_link"

        # Strategy 2: Search for specific missing data
        missing = candidate.get_missing_data_types()
        if missing and self.serpapi_client:
            enriched = await self._enrich_from_search(candidate, missing)
            if enriched:
                return enriched, "search"

        # No enrichment possible
        return None, None

    async def _enrich_from_link(
        self,
        candidate: ProductCandidate,
    ) -> Optional[ProductCandidate]:
        """Enrich by crawling the direct product link."""
        try:
            extraction = self.smart_crawler.extract_product(
                expected_name=candidate.name,
                product_type=candidate.product_type,
                primary_url=candidate.direct_product_link,
            )

            if extraction.success and extraction.data:
                # Merge extracted data into candidate
                return self._merge_extraction_into_candidate(candidate, extraction.data)
        except Exception as e:
            logger.warning(f"Link enrichment failed for {candidate.name}: {e}")

        return None

    async def _enrich_from_search(
        self,
        candidate: ProductCandidate,
        missing_types: List[str],
    ) -> Optional[ProductCandidate]:
        """Enrich by searching for specific missing data."""
        # Build targeted search queries based on what's missing
        queries = []

        if "tasting_notes" in missing_types:
            queries.append(f"{candidate.name} tasting notes review")
        if "pricing" in missing_types:
            queries.append(f"{candidate.name} price buy")
        if "images" in missing_types:
            queries.append(f"{candidate.name} bottle image")

        # Limit to 2 queries max to control API costs
        for query in queries[:2]:
            try:
                results = await self.serpapi_client.search(query, num_results=3)
                for result in results:
                    # Try to extract from each result
                    enriched = await self._try_extract_from_url(
                        candidate,
                        result.url,
                        missing_types,
                    )
                    if enriched:
                        return enriched
            except Exception as e:
                logger.warning(f"Search enrichment failed: {e}")

        return None

    async def _try_extract_from_url(
        self,
        candidate: ProductCandidate,
        url: str,
        missing_types: List[str],
    ) -> Optional[ProductCandidate]:
        """Try to extract missing data from a URL."""
        if not self.smart_crawler:
            return None

        try:
            extraction = self.smart_crawler.extract_product(
                expected_name=candidate.name,
                product_type=candidate.product_type,
                primary_url=url,
            )

            if extraction.success and extraction.data:
                return self._merge_extraction_into_candidate(candidate, extraction.data)
        except Exception:
            pass

        return None

    def _merge_extraction_into_candidate(
        self,
        candidate: ProductCandidate,
        extraction_data: Dict[str, Any],
    ) -> ProductCandidate:
        """Merge extraction data into candidate, preferring existing data."""
        # Create a copy with merged data
        merged = ProductCandidate(
            name=candidate.name,  # Keep original name
            brand=candidate.brand or extraction_data.get("brand"),
            extraction_source=candidate.extraction_source,
            source_url=candidate.source_url,
            product_type=candidate.product_type,
            abv=candidate.abv or extraction_data.get("abv"),
            age_statement=candidate.age_statement or extraction_data.get("age_statement"),
            description=candidate.description or extraction_data.get("description"),
            tasting_notes=candidate.tasting_notes or extraction_data.get("tasting_notes"),
            nose_description=candidate.nose_description or extraction_data.get("nose_description"),
            palate_flavors=candidate.palate_flavors or extraction_data.get("palate_flavors"),
            awards=candidate.awards + extraction_data.get("awards", []),
            ratings=candidate.ratings + extraction_data.get("ratings", []),
            images=candidate.images + extraction_data.get("images", []),
            prices=candidate.prices + extraction_data.get("prices", []),
            extraction_confidence=max(
                candidate.extraction_confidence,
                extraction_data.get("confidence", 0.5),
            ),
        )

        return merged

    async def _save(self, candidate: ProductCandidate) -> ProductSaveResult:
        """Save the candidate as a DiscoveredProduct."""
        from asgiref.sync import sync_to_async

        @sync_to_async
        def do_save():
            return save_discovered_product(
                extracted_data=candidate.to_extracted_data(),
                source_url=candidate.source_url,
                product_type=candidate.product_type,
                discovery_source=candidate.extraction_source.value,
                extraction_confidence=candidate.extraction_confidence,
                field_confidences=candidate.field_confidences,
                raw_content="",
            )

        return await do_save()

    def _get_product_completeness(self, product: DiscoveredProduct) -> int:
        """Calculate completeness score for an existing product."""
        score = 0

        if product.name: score += 20
        if product.brand: score += 10
        if product.product_type: score += 10
        if product.nose_description or product.palate_flavors: score += 15
        if product.description: score += 10
        if product.abv: score += 5
        if product.best_price: score += 10
        if product.images.exists(): score += 10
        if product.ratings.exists(): score += 5
        if product.awards_rel.exists(): score += 5

        return min(score, 100)
```

### 8.3 Updated Extractors

Each extractor now produces `ProductCandidate`:

```python
# crawler/discovery/competitions/competition_extractor.py

class CompetitionExtractor:
    """Extracts products from competition pages using BeautifulSoup parsers."""

    def extract(self, html: str, competition_key: str, year: int) -> List[ProductCandidate]:
        """Extract all products from a competition page."""
        parser = get_parser(competition_key)
        results = parser.parse(html, year)

        candidates = []
        for result in results:
            candidate = ProductCandidate.from_competition_result(result.to_dict())
            candidates.append(candidate)

        return candidates


# crawler/discovery/list_extractor.py

class ListPageExtractor:
    """Extracts products from list pages using AI."""

    async def extract(self, html: str, url: str, product_type: str) -> List[ProductCandidate]:
        """Extract all products from a list page."""
        response = await self.ai_client.extract_product_list(html, url)

        candidates = []
        for product_data in response.get("products", []):
            candidate = ProductCandidate(
                name=product_data.get("name", ""),
                brand=product_data.get("brand"),
                extraction_source=ExtractionSource.AI_LIST_EXTRACTION,
                source_url=url,
                direct_product_link=product_data.get("link"),
                product_type=product_type,
                tasting_notes=product_data.get("tasting_notes"),
                ratings=product_data.get("ratings", []),
                extraction_confidence=0.6,
            )
            candidates.append(candidate)

        return candidates


# crawler/discovery/single_extractor.py

class SingleProductExtractor:
    """Extracts a single product from a product page using AI."""

    async def extract(self, html: str, url: str, product_type: str) -> Optional[ProductCandidate]:
        """Extract product from a single product page."""
        response = await self.ai_client.enhance_from_crawler(html, url, product_type)

        if response.success:
            return ProductCandidate.from_ai_extraction(response.extracted_data, url)

        return None
```

### 8.4 Simplified Orchestrators

```python
# crawler/services/competition_orchestrator.py (simplified)

class CompetitionOrchestrator:
    """Orchestrates competition discovery using unified pipeline."""

    def __init__(self):
        self.extractor = CompetitionExtractor()
        self.pipeline = ProductPipeline(
            enable_enrichment=False,  # Competition products get enriched separately
        )

    async def discover(self, html: str, competition_key: str, year: int) -> DiscoveryResult:
        """Discover products from a competition page."""
        # Extract all candidates
        candidates = self.extractor.extract(html, competition_key, year)

        # Process through pipeline
        results = await self.pipeline.process_batch(
            candidates,
            skip_enrichment=True,  # Don't enrich during discovery
        )

        return DiscoveryResult(
            candidates_found=len(candidates),
            products_created=sum(1 for r in results if r.created),
            duplicates=sum(1 for r in results if r.was_duplicate),
        )


# crawler/services/discovery_orchestrator.py (simplified)

class DiscoveryOrchestrator:
    """Orchestrates generic search discovery using unified pipeline."""

    def __init__(self):
        self.list_extractor = ListPageExtractor()
        self.single_extractor = SingleProductExtractor()
        self.pipeline = ProductPipeline(
            enable_enrichment=True,  # Enable immediate enrichment
        )

    async def process_list_page(self, html: str, url: str, product_type: str):
        """Process a list page."""
        candidates = await self.list_extractor.extract(html, url, product_type)
        results = await self.pipeline.process_batch(candidates)
        return results

    async def process_single_page(self, html: str, url: str, product_type: str):
        """Process a single product page."""
        candidate = await self.single_extractor.extract(html, url, product_type)
        if candidate:
            return await self.pipeline.process(candidate)
        return None
```

---
