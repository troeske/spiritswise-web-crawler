# Generated manually for V2 Implementation
# Renames term_template to search_query, adds max_results, adds LIST_PAGE source type

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("crawler", "0039_source_tracker_v2_fields"),
    ]

    operations = [
        # Rename term_template to search_query in SearchTerm model
        migrations.RenameField(
            model_name="searchterm",
            old_name="term_template",
            new_name="search_query",
        ),
        # Update the help_text for the renamed field
        migrations.AlterField(
            model_name="searchterm",
            name="search_query",
            field=models.CharField(
                help_text="Complete search query to execute.",
                max_length=200,
            ),
        ),
        # Add max_results field to SearchTerm
        migrations.AddField(
            model_name="searchterm",
            name="max_results",
            field=models.IntegerField(
                default=10,
                help_text="Number of search results to crawl (1-20).",
                validators=[MinValueValidator(1), MaxValueValidator(20)],
            ),
        ),
        # Note: LIST_PAGE is added to CrawledSourceTypeChoices enum in models.py
        # TextChoices enums don't require migrations - the validation happens at Python level
    ]
