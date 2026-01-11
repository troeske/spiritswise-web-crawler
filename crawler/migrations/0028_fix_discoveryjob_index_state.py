# Generated manually to fix migration state - index doesn't exist in DB
from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Fix migration state for discovery_j_schedul_d7a44c_idx index.

    This index was defined in 0021 for the old 'schedule' FK but was implicitly
    removed when the field was deleted in 0026. However, Django's migration state
    still thinks it exists. We use SeparateDatabaseAndState to update only the
    state without trying to touch the database.
    """

    dependencies = [
        ("crawler", "0027_remove_categoryinsight_unique_category_insight_and_more"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.RemoveIndex(
                    model_name="discoveryjob",
                    name="discovery_j_schedul_d7a44c_idx",
                ),
            ],
            database_operations=[
                # No database operations - index doesn't exist
            ],
        ),
    ]
