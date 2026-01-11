"""
AI Extractors for Award Site Detail Pages.

This module contains AI-powered extractors that extract structured product data
from award site detail pages using LLM prompts.

Extractors:
- AIExtractor: Unified AI extractor for all award sources

Prompts:
- IWSC_EXTRACTION_PROMPT: Prompt for IWSC detail pages
- DWWA_PORT_EXTRACTION_PROMPT: Prompt for DWWA port wine pages
- GENERAL_EXTRACTION_PROMPT: Generic extraction prompt
"""

from .extraction_prompts import (
    IWSC_EXTRACTION_PROMPT,
    DWWA_PORT_EXTRACTION_PROMPT,
    GENERAL_EXTRACTION_PROMPT,
)
from .ai_extractor import AIExtractor

__all__ = [
    "AIExtractor",
    "IWSC_EXTRACTION_PROMPT",
    "DWWA_PORT_EXTRACTION_PROMPT",
    "GENERAL_EXTRACTION_PROMPT",
]
