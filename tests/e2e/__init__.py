"""
E2E Tests for V2 Architecture.

This package contains end-to-end tests that use REAL external services:
- AI Enhancement Service (OpenAI via service)
- SerpAPI for enrichment searches
- ScrapingBee for JavaScript rendering
- Wayback Machine for archival

IMPORTANT:
- These tests do NOT mock external services
- All data created is PRESERVED for manual verification
- Tests use real competition URLs from IWSC, SFWSC, DWWA
- Estimated cost per full run: $15-25

Structure:
    conftest.py          - Shared fixtures and test configuration
    flows/               - Individual flow test modules
    utils/               - Test utilities (URLs, verification, reporting)
"""
