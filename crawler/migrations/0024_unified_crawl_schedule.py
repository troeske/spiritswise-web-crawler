"""
Migration: Replace old CrawlSchedule with unified CrawlSchedule model.

This migration:
1. Drops the old crawl_schedule table (with source FK and limited fields)
2. Creates the new unified crawl_schedule table with all new fields
"""

import uuid
from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0023_quota_usage"),
    ]

    operations = [
        # Drop the old table completely
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS crawl_schedule;",
            reverse_sql="",  # Can't reverse this
        ),

        # Create the new unified CrawlSchedule model
        migrations.CreateModel(
            name="CrawlSchedule",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("name", models.CharField(max_length=200)),
                ("slug", models.SlugField(max_length=100, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "category",
                    models.CharField(
                        choices=[
                            ("competition", "Competition/Awards"),
                            ("discovery", "Discovery Search"),
                            ("retailer", "Retailer Monitoring"),
                        ],
                        db_index=True,
                        default="discovery",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                (
                    "frequency",
                    models.CharField(
                        choices=[
                            ("hourly", "Hourly"),
                            ("every_6_hours", "Every 6 Hours"),
                            ("every_12_hours", "Every 12 Hours"),
                            ("daily", "Daily"),
                            ("weekly", "Weekly"),
                            ("biweekly", "Bi-weekly"),
                            ("monthly", "Monthly"),
                            ("quarterly", "Quarterly"),
                        ],
                        default="daily",
                        max_length=20,
                    ),
                ),
                (
                    "priority",
                    models.IntegerField(
                        default=5,
                        help_text="Higher priority schedules run first (1-10)",
                    ),
                ),
                ("last_run", models.DateTimeField(blank=True, null=True)),
                ("next_run", models.DateTimeField(blank=True, db_index=True, null=True)),
                (
                    "search_terms",
                    models.JSONField(
                        default=list,
                        help_text='\n        For COMPETITION: List of competition identifiers with years\n            e.g., ["iwsc:2024", "iwsc:2025", "wwa:2024"]\n        For DISCOVERY: List of search queries\n            e.g., ["best single malt whisky 2024", "award winning bourbon"]\n        ',
                    ),
                ),
                (
                    "max_results_per_term",
                    models.IntegerField(
                        default=10,
                        help_text="Maximum results to process per search term",
                    ),
                ),
                (
                    "product_types",
                    models.JSONField(
                        default=list,
                        help_text="Filter to specific product types: ['whiskey', 'port_wine', etc.]",
                    ),
                ),
                (
                    "exclude_domains",
                    models.JSONField(
                        default=list,
                        help_text="Domains to exclude from results",
                    ),
                ),
                (
                    "base_url",
                    models.URLField(
                        blank=True,
                        help_text="Base URL for competition results page (COMPETITION only)",
                        max_length=500,
                    ),
                ),
                ("robots_txt_compliant", models.BooleanField(default=True)),
                ("tos_compliant", models.BooleanField(default=True)),
                (
                    "daily_quota",
                    models.IntegerField(
                        default=100,
                        help_text="Maximum API calls per day for this schedule",
                    ),
                ),
                (
                    "monthly_quota",
                    models.IntegerField(
                        default=2000,
                        help_text="Maximum API calls per month for this schedule",
                    ),
                ),
                ("total_runs", models.IntegerField(default=0)),
                ("total_products_found", models.IntegerField(default=0)),
                ("total_products_new", models.IntegerField(default=0)),
                ("total_products_duplicate", models.IntegerField(default=0)),
                ("total_errors", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "config",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Additional category-specific configuration",
                    ),
                ),
            ],
            options={
                "db_table": "crawl_schedule",
                "ordering": ["-priority", "name"],
            },
        ),

        # Add indexes
        migrations.AddIndex(
            model_name="crawlschedule",
            index=models.Index(
                fields=["is_active", "next_run"],
                name="crawl_sched_is_acti_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="crawlschedule",
            index=models.Index(
                fields=["category", "is_active"],
                name="crawl_sched_categor_idx",
            ),
        ),
    ]
