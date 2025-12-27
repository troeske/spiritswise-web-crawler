# SpiritsWise Web Crawler

A state-of-the-art web crawler system designed to build the world's most comprehensive whiskey and port wine database.

## Overview

This crawler system discovers and extracts product information from:
- **Retailers & Aggregators**: The Whisky Exchange, Master of Malt, Wine-Searcher
- **Producer Websites**: Distilleries and wineries
- **Competition Results**: IWSC, SFWSC, World Whiskies Awards, Decanter World Wine Awards
- **Reviews & Articles**: Expert reviews and tasting notes

## Key Features

- **Smart Access Layer**: Multi-tiered fetching (httpx → Playwright → ScrapingBee) to handle age gates cost-effectively
- **Prestige-Led Discovery**: Prioritizes award-winning products from major competitions
- **Hub & Spoke Discovery**: Uses retailers to discover producer websites
- **Link Rot Mitigation**: Wayback Machine archiving with health monitoring
- **AI-Powered Extraction**: GPT-4 for product data extraction and enrichment

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DISCOVERY LAYER                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Hub & Spoke  │  │ Prestige-Led │  │   SerpAPI    │          │
│  │  Discovery   │  │  Discovery   │  │   Search     │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     SMART ROUTER                                 │
│  Tier 1: httpx + Cookies  →  Tier 2: Playwright  →  Tier 3: API │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  AI EXTRACTION (GPT-4)                          │
│  Product Detection → Field Extraction → Enrichment              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     STORAGE LAYER                                │
│  PostgreSQL (Products, Articles) + Redis (Queue, Cache)         │
└─────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
spiritswise-web-crawler/
├── specs/                    # Architecture specifications
│   ├── web-crawler-spec-v3.md    # Main specification
│   ├── web-crawler-architecture.md
│   └── web_crawler_spec_v2.md
├── fixtures/                 # Database seed data
│   ├── whiskey_sources.json
│   ├── whiskey_keywords.json
│   ├── port_wine_sources.json
│   └── port_wine_keywords.json
├── crawler/                  # Django app (coming soon)
└── README.md
```

## Technology Stack

- **Framework**: Django + Celery
- **Fetching**: httpx, Playwright, ScrapingBee
- **Search**: SerpAPI
- **AI**: OpenAI GPT-4 (via spiritswise-ai-enhancement-service)
- **Storage**: PostgreSQL, Redis
- **Archiving**: Wayback Machine API

## Related Services

- [spiritswise-ai-enhancement-service](https://github.com/troeske/spiritswise-ai-enhancement-service) - AI extraction and enrichment API

## Status

**Phase 1**: Specification & Architecture - Complete
**Phase 2**: Implementation - In Progress

## License

Proprietary - SpiritsWise
