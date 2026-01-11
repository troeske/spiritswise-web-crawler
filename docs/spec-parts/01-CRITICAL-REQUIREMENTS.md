# Part 1: Executive Summary & Critical Requirements
*Lines 1-91 from FLOW_COMPARISON_ANALYSIS.md*

## Executive Summary

This document analyzes three product discovery flows in the crawler and proposes a unified architecture. Since we are in development phase (not production), we can make breaking changes without backward compatibility concerns.

**The Three Flows:**
1. **Award/Competition Discovery** - Creates skeleton products from structured competition pages
2. **Generic Search List Pages** - Extracts multiple products from blog/review articles
3. **Single Product Enhancement** - Full extraction from individual product pages

**Key Insight:** All three flows ultimately do the same thing - discover product data and save it. They differ only in:
- How they identify products (structured parser vs AI vs direct URL)
- How much data they extract initially
- When/how they enrich incomplete data

---

## CRITICAL REQUIREMENTS

### Requirement 1: Mandatory Tasting Profile

A product **CANNOT** be marked as COMPLETE or VERIFIED without tasting profile data.

**Minimum Required for COMPLETE:**
- `palate_flavors` (at least 2 tags) OR `palate_description` OR `initial_taste`

**Additional Required for VERIFIED:**
- Nose profile: `nose_description` OR `primary_aromas` (2+ tags)
- Finish profile: `finish_description` OR `finish_flavors` (2+ tags)
- Multi-source verification: `source_count >= 2`

### Requirement 2: Multi-Source Verification

Products discovered from one source **MUST** be enriched from additional sources to:
1. Verify extracted data accuracy (if 2 sources agree, field is verified)
2. Fill in missing fields (especially tasting profile)
3. Build confidence through consensus

**Target:** 2-3 sources per product before VERIFIED status.

### Requirement 3: No JSON Blobs for Searchable Data

**WRONG (current implementation):**
```python
extracted_data = models.JSONField(default=dict)  # Catch-all blob
enriched_data = models.JSONField(default=dict)   # Another blob
taste_profile = models.JSONField(default=dict)   # Yet another blob
```

**RIGHT (new implementation):**
```python
# Individual searchable/filterable columns
name = models.CharField(max_length=500)
abv = models.DecimalField(...)
palate_description = models.TextField(...)
finish_length = models.IntegerField(...)

# JSONField ONLY for:
# - Arrays of tags (primary_aromas, palate_flavors) - OK
# - Rarely-queried metadata
# - Truly dynamic/extensible data
```

### Requirement 4: Model Split

Keep separation between:
- **DiscoveredProduct** - Core product data + tasting profile + status
- **WhiskeyDetails** - Whiskey-only fields (distillery, peated, peat_level, mash_bill, etc.)
- **PortWineDetails** - Port-only fields (style, quinta, harvest_year, grape_varieties, etc.)
