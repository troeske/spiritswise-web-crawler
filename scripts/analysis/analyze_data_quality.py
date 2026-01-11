#!/usr/bin/env python
"""Analyze data quality of products in the dev database."""
import os
import sys
import json
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django
django.setup()

from crawler.models import DiscoveredProduct, ProductAward

products = DiscoveredProduct.objects.all()
total = products.count()

by_status = {}
by_type = {}
metrics = {"abv": 0, "description": 0, "region": 0, "source_url": 0, "nose": 0, "palate": 0, "finish": 0, "flavors": 0, "food_pairings": 0, "age_statement": 0, "volume_ml": 0, "brand": 0, "category": 0}
completeness = {}
awards_count = 0

for p in products:
    s = p.status or "unknown"
    by_status[s] = by_status.get(s, 0) + 1

    t = p.product_type or "unknown"
    by_type[t] = by_type.get(t, 0) + 1

    sc = p.completeness_score or 0
    bucket = f"{(sc // 10) * 10}-{(sc // 10) * 10 + 9}"
    completeness[bucket] = completeness.get(bucket, 0) + 1

    if p.abv: metrics["abv"] += 1
    if p.description: metrics["description"] += 1
    if p.region: metrics["region"] += 1
    if p.source_url: metrics["source_url"] += 1
    if p.nose_description: metrics["nose"] += 1
    if p.palate_description: metrics["palate"] += 1
    if p.finish_description: metrics["finish"] += 1
    if p.palate_flavors: metrics["flavors"] += 1
    if p.food_pairings: metrics["food_pairings"] += 1
    if p.age_statement: metrics["age_statement"] += 1
    if p.volume_ml: metrics["volume_ml"] += 1
    if p.brand: metrics["brand"] += 1
    if p.category: metrics["category"] += 1

    if ProductAward.objects.filter(product=p).exists():
        awards_count += 1

# Sample best products
samples = []
for p in products.order_by('-completeness_score')[:5]:
    samples.append({
        "id": str(p.id), "name": p.name[:60], "status": p.status, "type": p.product_type,
        "score": p.completeness_score, "abv": str(p.abv) if p.abv else None,
        "region": p.region, "has_nose": bool(p.nose_description),
        "has_palate": bool(p.palate_description), "has_finish": bool(p.finish_description),
        "flavors_count": len(p.palate_flavors) if p.palate_flavors else 0,
        "awards": ProductAward.objects.filter(product=p).count()
    })

# Sample skeleton products
skeletons = []
for p in products.filter(status="skeleton").order_by('-discovered_at')[:5]:
    skeletons.append({
        "id": str(p.id), "name": p.name[:60], "type": p.product_type,
        "score": p.completeness_score, "discovered": p.discovered_at.isoformat() if p.discovered_at else None
    })

result = {
    "timestamp": datetime.now().isoformat(),
    "total_products": total,
    "by_status": by_status,
    "by_product_type": by_type,
    "data_quality_metrics": metrics,
    "completeness_distribution": completeness,
    "products_with_awards": awards_count,
    "sample_best_products": samples,
    "sample_skeletons": skeletons
}

print(json.dumps(result, indent=2))
