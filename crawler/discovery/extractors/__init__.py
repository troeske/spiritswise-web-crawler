"""
AI Extractors for Award Site Detail Pages.

This module contains AI-powered extractors that extract structured product data
from award site detail pages using LLM prompts.

Extractors:
- AIExtractorV2: V2 AI extractor for all award sources (migrated from V1)
- AIExtractor: Alias for AIExtractorV2 for backward compatibility

Prompts:
- IWSC_EXTRACTION_PROMPT: Prompt for IWSC detail pages
- DWWA_PORT_EXTRACTION_PROMPT: Prompt for DWWA port wine pages
- GENERAL_EXTRACTION_PROMPT: Generic extraction prompt

V1→V2 Migration: V1 ai_extractor.py removed. Use ai_extractor_v2.py instead.
"""

from .extraction_prompts import (
    IWSC_EXTRACTION_PROMPT,
    DWWA_PORT_EXTRACTION_PROMPT,
    GENERAL_EXTRACTION_PROMPT,
)
# V1→V2 Migration: Import V2 extractor with backward-compatible alias
from .ai_extractor_v2 import AIExtractorV2, get_ai_extractor_v2

# Backward-compatible alias
AIExtractor = AIExtractorV2
get_ai_extractor = get_ai_extractor_v2

__all__ = [
    "AIExtractorV2",
    "AIExtractor",  # Alias for backward compatibility
    "get_ai_extractor_v2",
    "get_ai_extractor",  # Alias for backward compatibility
    "IWSC_EXTRACTION_PROMPT",
    "DWWA_PORT_EXTRACTION_PROMPT",
    "GENERAL_EXTRACTION_PROMPT",
]
