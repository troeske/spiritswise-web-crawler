# Generated manually to fix table naming inconsistencies

from django.db import migrations, connection


def rename_table_if_exists(old_name, new_name):
    """Generate a function that renames a table only if it exists."""
    def do_rename(apps, schema_editor):
        with connection.cursor() as cursor:
            # Check if the old table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
                [old_name]
            )
            if cursor.fetchone():
                cursor.execute(f'ALTER TABLE "{old_name}" RENAME TO "{new_name}";')
    return do_rename


def reverse_rename_table_if_exists(old_name, new_name):
    """Generate a function that reverses table rename only if applicable."""
    def do_reverse(apps, schema_editor):
        with connection.cursor() as cursor:
            # Check if the new table exists (to reverse to old name)
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?;",
                [new_name]
            )
            if cursor.fetchone():
                cursor.execute(f'ALTER TABLE "{new_name}" RENAME TO "{old_name}";')
    return do_reverse


class Migration(migrations.Migration):
    """
    Fix table naming (plural to singular).

    Renames (if plural versions exist from older schema):
    - crawled_sources -> crawled_source
    - new_releases -> new_release
    - price_alerts -> price_alert
    - product_candidates -> product_candidate
    - product_field_sources -> product_field_source
    - product_prices -> product_price

    Note: SourceMetrics and AlertRule are already created in migrations 0012/0013,
    so we don't recreate them here.
    """

    dependencies = [
        ("crawler", "0030_align_field_attributes"),
    ]

    operations = [
        # ===== Rename plural tables to singular (conditional) =====
        migrations.RunPython(
            rename_table_if_exists("crawled_sources", "crawled_source"),
            reverse_rename_table_if_exists("crawled_sources", "crawled_source"),
        ),
        migrations.RunPython(
            rename_table_if_exists("new_releases", "new_release"),
            reverse_rename_table_if_exists("new_releases", "new_release"),
        ),
        migrations.RunPython(
            rename_table_if_exists("price_alerts", "price_alert"),
            reverse_rename_table_if_exists("price_alerts", "price_alert"),
        ),
        migrations.RunPython(
            rename_table_if_exists("product_candidates", "product_candidate"),
            reverse_rename_table_if_exists("product_candidates", "product_candidate"),
        ),
        migrations.RunPython(
            rename_table_if_exists("product_field_sources", "product_field_source"),
            reverse_rename_table_if_exists("product_field_sources", "product_field_source"),
        ),
        migrations.RunPython(
            rename_table_if_exists("product_prices", "product_price"),
            reverse_rename_table_if_exists("product_prices", "product_price"),
        ),
    ]
