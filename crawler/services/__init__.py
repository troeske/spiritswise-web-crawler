"""
Services module for the Web Crawler.

Contains:
- ai_client: AI Enhancement Service API client
- content_processor: Content processing pipeline
"""

from crawler.services.ai_client import AIEnhancementClient, EnhancementResult
from crawler.services.content_processor import ContentProcessor

__all__ = [
    "AIEnhancementClient",
    "EnhancementResult",
    "ContentProcessor",
]
