# Enrichment Results Comparison - 2026-01-13

## Summary: SIGNIFICANT IMPROVEMENT ACHIEVED

After implementing the fixes, the enrichment quality has **improved significantly** compared to the morning run.

---

## Key Metrics Comparison

| Product | Morning Fields | Evening Fields | Morning ECP | Evening ECP |
|---------|---------------|----------------|-------------|-------------|
| SMWS 1.292 | 16 | 16 | 0.0% | **11.86%** |
| GlenAllachie 10 YO | 21 | **31** | 0.0% | **28.81%** |
| Ballantine's 10 YO | 16 | 16 | 0.0% | **10.17%** |

---

## Improvements Made

### 1. QualityGate Version Fix
- **Bug:** EnrichmentOrchestratorV3 was using QualityGateV2 for status assessment
- **Fix:** Added `_get_quality_gate()` override to return V3 quality gate
- **Impact:** Consistent status reporting between enrichment and verification

### 2. FieldGroups Now Created Programmatically
- **Bug:** whiskey_pipeline_v3.json fixture failed to load (wrong format)
- **Fix:** Create FieldGroups programmatically after ProductTypeConfig
- **Impact:** ECP calculation now works (was always 0.0 before)

### 3. HTTP 403 Blocking Mitigation
- **Bug:** Outdated Chrome/120 User-Agent, no proper browser headers
- **Fix:** Updated to Chrome/131, added full browser headers (Accept, Sec-Fetch-*, etc.)
- **Impact:** More sources successfully fetched

### 4. Rate Limiting Prevention
- **Fix:** Added random 0.5-1.5s delay between requests
- **Impact:** Reduced 403 errors from rate limiting

---

## GlenAllachie Product: Exceptional Enrichment

The GlenAllachie product shows the most dramatic improvement:

### Morning Result
```
fields_enriched: 21
ecp_total: 0.0
awards: 1 (IWSC only)
```

### Evening Result
```
fields_enriched: 31 (+10 new fields!)
ecp_total: 28.81% (vs 0%)
awards: 5 awards from multiple competitions:
  - IWSC 2025: Silver (93)
  - World Whiskies Awards 2025: World's Best Single Malt
  - San Francisco World Spirits Competition: Double Gold
  - International Spirits Challenge 2024: Gold
  - Scotch Whisky Masters 2025: Gold

New fields captured:
  - balance: "Perfectly balanced flavours of sweet spice..."
  - overall_complexity: "Satisfyingly complex yet perfectly balanced"
  - uniqueness: "Showcases our independent approach..."
  - drinkability: "Full-bodied whisky that can be enjoyed your way"
  - natural_color: true
  - non_chill_filtered: true
  - peated: false
  - peat_level: "unpeated"
  - images: Product image URL
  - secondary_aromas: ["cinnamon", "espresso", "sticky raisins"]
```

---

## HTTP 403 Status

### Sites Still Blocked
Some sites continue to block despite the improvements:
- whiskybase.com (403)
- reddit.com (403)
- smws.com (403)

### Sites Now Working
Many sites that were blocked earlier now work:
- theglenallachie.com ✓
- wordsofwhisky.com ✓
- connosr.com ✓
- bondston.com ✓
- newmake.smwsa.com ✓

### Future Improvements for 403 Sites
1. **Consider using a proxy rotation service** (ScrapingBee, Bright Data)
2. **Implement cookie handling** for sites requiring session
3. **Add Cloudflare bypass** for protected sites
4. **Use Playwright/Puppeteer** for JavaScript-required sites

---

## Files Modified

| File | Change |
|------|--------|
| `crawler/services/enrichment_orchestrator_v3.py` | Added `_get_quality_gate()` override |
| `crawler/services/enrichment_orchestrator_v2.py` | Updated headers, added rate limiting |
| `tests/e2e/flows/test_iwsc_flow.py` | Programmatic FieldGroup creation |

---

## Conclusion

The enrichment pipeline is now functioning at a higher level than the morning run:
- **ECP calculation works** (critical for COMPLETE status determination)
- **More fields captured** (especially for GlenAllachie: +10 fields)
- **Multiple awards discovered** (from various competitions)
- **Better source success rate** (improved headers)

The remaining 403 errors from sites like Reddit and WhiskyBase require more advanced techniques (proxies, browser automation) which can be addressed in a future task.
