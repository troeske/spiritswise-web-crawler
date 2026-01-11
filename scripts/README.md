# Scripts Directory

This directory contains standalone scripts for testing, debugging, analysis, and utility operations.

## Directory Structure

### `/analysis`
Scripts for analyzing data quality, enrichment issues, and product details.
- `analyze_data_quality.py` - Analyze overall data quality metrics
- `analyze_enrichment_issues.py` - Investigate enrichment failures
- `analyze_whiskey_details.py` - Analyze whiskey product details

### `/debug`
Debug and ad-hoc test scripts for investigating specific issues.
- `debug_full_pipeline.py` - Debug the full crawl pipeline
- `debug_hallucination.py` - Debug AI hallucination issues
- `test_*.py` - Various debug test scripts

### `/e2e`
End-to-end test scripts for full flow testing.
- `e2e_medal_winners_test.py` - Test medal winner extraction
- `e2e_unified_scheduler_test.py` - Test unified scheduler
- `e2e_data_quality_test.py` - Test data quality metrics
- `run_e2e_flows.py` - Run all E2E flows
- `run_e2e_test.py` - Run E2E test suite
- `run_full_e2e.bat` - Windows batch script for full E2E

### `/utils`
Utility scripts for common operations.
- `check_status.py` - Check system status
- `enrich_from_cache.py` - Enrich products from cached data
- `run_enrichment.py` - Run product enrichment
- `run_enrichment_quiet.py` - Run enrichment (quiet mode)
- `show_products.py` - Display product information

## Usage

Run scripts from the project root:
```bash
python scripts/analysis/analyze_data_quality.py
python scripts/e2e/run_e2e_test.py --help
```

## Note

These scripts are for development and testing purposes. For production operations, use the Django management commands in `crawler/management/commands/`.
