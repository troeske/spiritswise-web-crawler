# 07 - Multi-Source Verification Pipeline

> Extracted from `FLOW_COMPARISON_ANALYSIS.md` lines 1461-1558

---

## 7. Multi-Source Verification Pipeline

### 7.1 Verification Flow

```python
class VerificationPipeline:
    """
    Pipeline that enriches products from multiple sources.
    Goal: Every product should be verified from 2+ sources before VERIFIED status.
    """

    TARGET_SOURCES = 3
    MIN_SOURCES_FOR_VERIFIED = 2

    ENRICHMENT_STRATEGIES = {
        "tasting_notes": [
            "{name} tasting notes review",
            "{name} nose palate finish",
            "{brand} {name} whisky review",
        ],
        "pricing": [
            "{name} buy price",
            "{name} whisky exchange price",
        ],
    }

    async def verify_product(self, candidate: ProductCandidate) -> VerificationResult:
        """
        Steps:
        1. Save initial product (from first source)
        2. Identify missing/unverified fields
        3. Search for additional sources
        4. Extract data from each source
        5. Merge and verify data (if values match = verified)
        6. Update completeness and status
        """
        product = await self._get_or_create_product(candidate)
        sources_used = 1

        missing = self._get_missing_critical_fields(product)
        needs_verification = self._get_unverified_fields(product)

        if missing or needs_verification or sources_used < self.TARGET_SOURCES:
            search_results = await self._search_additional_sources(product, missing)

            for source_url in search_results[:self.TARGET_SOURCES - 1]:
                extraction = await self._extract_from_source(source_url, product)
                if extraction.success:
                    await self._merge_and_verify(product, extraction)
                    sources_used += 1

        product.source_count = sources_used
        product.completeness_score = calculate_completeness(product)
        product.status = determine_status(product)
        await self._save_product(product)

        return VerificationResult(product=product, sources_used=sources_used)

    def _get_missing_critical_fields(self, product) -> List[str]:
        """Especially: palate, nose, finish, abv, description."""
        missing = []
        if not product.palate_flavors and not product.palate_description:
            missing.append("palate")
        if not product.nose_description and not product.primary_aromas:
            missing.append("nose")
        if not product.finish_description and not product.finish_flavors:
            missing.append("finish")
        return missing

    async def _merge_and_verify(self, product, extraction):
        """
        Merge new data, marking verified fields.
        If values match = field is verified!
        """
        verified = list(product.verified_fields or [])

        for field, new_value in extraction.data.items():
            if not new_value:
                continue

            current_value = getattr(product, field, None)

            if current_value is None:
                # Field was missing - add it
                setattr(product, field, new_value)
            elif self._values_match(current_value, new_value):
                # Values match - field is verified!
                if field not in verified:
                    verified.append(field)
            else:
                # Values differ - log conflict
                await self._log_conflict(product, field, current_value, new_value)

        product.verified_fields = verified
```

---
