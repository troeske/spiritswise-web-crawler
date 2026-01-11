# Generated manually to fix schema mismatches between models and database

from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):
    """
    Fix schema mismatches by dropping and recreating affected tables.

    All affected tables are empty, so no data loss.
    Uses raw SQL to drop tables then SeparateDatabaseAndState to recreate.
    """

    dependencies = [
        ("crawler", "0028_fix_discoveryjob_index_state"),
    ]

    operations = [
        # ===== PortWineDetails - complete schema mismatch =====
        # First, remove from state only (no DB operation since we'll drop the table)
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="PortWineDetails"),
            ],
            database_operations=[
                # Drop the table with wrong schema
                migrations.RunSQL("DROP TABLE IF EXISTS port_wine_details;", ""),
            ],
        ),
        # Then recreate with correct schema
        migrations.CreateModel(
            name="PortWineDetails",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("style", models.CharField(max_length=20)),
                ("indication_age", models.CharField(blank=True, max_length=50, null=True)),
                ("harvest_year", models.IntegerField(blank=True, null=True)),
                ("bottling_year", models.IntegerField(blank=True, null=True)),
                ("grape_varieties", models.JSONField(blank=True, default=list)),
                ("quinta", models.CharField(blank=True, max_length=200, null=True)),
                ("douro_subregion", models.CharField(blank=True, max_length=20, null=True)),
                ("producer_house", models.CharField(max_length=200)),
                ("aging_vessel", models.CharField(blank=True, max_length=200, null=True)),
                ("decanting_required", models.BooleanField(default=False)),
                ("drinking_window", models.CharField(blank=True, max_length=50, null=True)),
                ("product", models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="port_details",
                    to="crawler.discoveredproduct",
                    help_text="The product these details belong to",
                )),
            ],
            options={
                "db_table": "port_wine_details",
                "verbose_name": "Port Wine Details",
                "verbose_name_plural": "Port Wine Details",
            },
        ),

        # ===== BrandSource - missing mention_count, mention_type =====
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="BrandSource"),
            ],
            database_operations=[
                migrations.RunSQL("DROP TABLE IF EXISTS brand_source;", ""),
            ],
        ),
        migrations.CreateModel(
            name="BrandSource",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("extracted_at", models.DateTimeField(auto_now_add=True)),
                ("extraction_confidence", models.FloatField(default=0.0)),
                ("mention_type", models.CharField(blank=True, max_length=50)),
                ("mention_count", models.PositiveIntegerField(default=1)),
                ("brand", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sources",
                    to="crawler.discoveredbrand",
                )),
                ("source", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="brand_sources",
                    to="crawler.crawledsource",
                )),
            ],
            options={
                "db_table": "brand_source",
                "verbose_name": "Brand Source",
                "verbose_name_plural": "Brand Sources",
            },
        ),

        # ===== ProductImage - missing is_primary =====
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="ProductImage"),
            ],
            database_operations=[
                migrations.RunSQL("DROP TABLE IF EXISTS product_image;", ""),
            ],
        ),
        migrations.CreateModel(
            name="ProductImage",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("url", models.URLField()),
                ("image_type", models.CharField(max_length=20)),
                ("source", models.CharField(blank=True, max_length=100)),
                ("width", models.PositiveIntegerField(blank=True, null=True)),
                ("height", models.PositiveIntegerField(blank=True, null=True)),
                ("is_primary", models.BooleanField(default=False)),
                ("product", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="images",
                    to="crawler.discoveredproduct",
                )),
            ],
            options={
                "db_table": "product_image",
                "verbose_name": "Product Image",
                "verbose_name_plural": "Product Images",
            },
        ),

        # ===== ProductRating - missing review_count, updated_at =====
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="ProductRating"),
            ],
            database_operations=[
                migrations.RunSQL("DROP TABLE IF EXISTS product_rating;", ""),
            ],
        ),
        migrations.CreateModel(
            name="ProductRating",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("source", models.CharField(max_length=100)),
                ("source_country", models.CharField(blank=True, max_length=100)),
                ("score", models.FloatField()),
                ("max_score", models.FloatField(default=100.0)),
                ("review_count", models.PositiveIntegerField(blank=True, null=True)),
                ("reviewer", models.CharField(blank=True, max_length=200)),
                ("review_url", models.URLField(blank=True)),
                ("date", models.DateField(blank=True, null=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="ratings",
                    to="crawler.discoveredproduct",
                )),
            ],
            options={
                "db_table": "product_rating",
                "verbose_name": "Product Rating",
                "verbose_name_plural": "Product Ratings",
            },
        ),

        # ===== ProductSource - missing mention_count, mention_type =====
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name="ProductSource"),
            ],
            database_operations=[
                migrations.RunSQL("DROP TABLE IF EXISTS product_source;", ""),
            ],
        ),
        migrations.CreateModel(
            name="ProductSource",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("extracted_at", models.DateTimeField(auto_now_add=True)),
                ("extraction_confidence", models.FloatField(default=0.0)),
                ("fields_extracted", models.JSONField(blank=True, default=list)),
                ("mention_type", models.CharField(blank=True, max_length=50)),
                ("mention_count", models.PositiveIntegerField(default=1)),
                ("product", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sources",
                    to="crawler.discoveredproduct",
                )),
                ("source", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="product_sources",
                    to="crawler.crawledsource",
                )),
            ],
            options={
                "db_table": "product_source",
                "verbose_name": "Product Source",
                "verbose_name_plural": "Product Sources",
            },
        ),
    ]
