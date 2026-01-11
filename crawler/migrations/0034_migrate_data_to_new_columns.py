# Generated manually for data migration from JSON blobs to individual columns

from django.db import migrations


def migrate_json_to_columns(apps, schema_editor):
    """
    Migrate data from taste_profile JSON blob to individual columns.
    Also migrate data from enriched_data and extracted_data where appropriate.
    Update legacy status values to new model.
    """
    DiscoveredProduct = apps.get_model("crawler", "DiscoveredProduct")

    for product in DiscoveredProduct.objects.all():
        updated_fields = []

        # Combine all JSON sources
        taste_profile = product.taste_profile or {}
        enriched_data = product.enriched_data or {}
        extracted_data = product.extracted_data or {}

        # Migrate palate_description from taste_profile
        if not product.palate_description:
            palate_desc = (
                taste_profile.get("palate")
                or enriched_data.get("palate")
                or enriched_data.get("palate_description")
            )
            if palate_desc:
                product.palate_description = palate_desc
                updated_fields.append("palate_description")

        # Migrate finish_description from taste_profile
        if not product.finish_description:
            finish_desc = (
                taste_profile.get("finish")
                or enriched_data.get("finish")
                or enriched_data.get("finish_description")
            )
            if finish_desc:
                product.finish_description = finish_desc
                updated_fields.append("finish_description")

        # Migrate nose_description if empty
        if not product.nose_description:
            nose_desc = (
                taste_profile.get("nose")
                or enriched_data.get("nose")
                or enriched_data.get("nose_description")
            )
            if nose_desc:
                product.nose_description = nose_desc
                updated_fields.append("nose_description")

        # Migrate flavor_tags to palate_flavors if empty
        if not product.palate_flavors or product.palate_flavors == []:
            flavor_tags = (
                taste_profile.get("flavor_tags")
                or enriched_data.get("flavor_tags")
                or enriched_data.get("palate_flavors")
            )
            if flavor_tags and isinstance(flavor_tags, list):
                product.palate_flavors = flavor_tags
                updated_fields.append("palate_flavors")

        # Map legacy status to new status model
        status_mapping = {
            "pending": "incomplete",
            "skeleton": "incomplete",
            "approved": "partial",  # Approved means it was reviewed but may not have tasting
            "duplicate": "merged",  # Map duplicate to merged
        }

        if product.status in status_mapping:
            product.status = status_mapping[product.status]
            updated_fields.append("status")

        # Recalculate status based on available data
        has_palate = bool(
            (product.palate_flavors and len(product.palate_flavors) >= 2)
            or product.palate_description
            or product.initial_taste
        )
        has_nose = bool(
            product.nose_description
            or (product.primary_aromas and len(product.primary_aromas) >= 2)
        )
        has_finish = bool(
            product.finish_description
            or (product.finish_flavors and len(product.finish_flavors) >= 2)
        )

        # Calculate completeness score (simplified version)
        score = 0

        # Identification (15 points)
        if product.name:
            score += 10
        if product.brand_id:
            score += 5

        # Basic info (15 points)
        if product.product_type:
            score += 5
        if product.abv:
            score += 5
        # Check for description in enriched_data since field may not exist
        has_description = (
            enriched_data.get("description")
            or extracted_data.get("description")
        )
        if has_description:
            score += 5

        # Tasting profile (40 points)
        # Palate (20 points)
        palate_score = 0
        if product.palate_flavors and len(product.palate_flavors) >= 2:
            palate_score += 10
        if product.palate_description or product.initial_taste:
            palate_score += 5
        if product.mid_palate_evolution:
            palate_score += 3
        if product.mouthfeel:
            palate_score += 2
        score += min(palate_score, 20)

        # Nose (10 points)
        nose_score = 0
        if product.nose_description:
            nose_score += 5
        if product.primary_aromas and len(product.primary_aromas) >= 2:
            nose_score += 5
        score += min(nose_score, 10)

        # Finish (10 points)
        finish_score = 0
        if product.finish_description or product.final_notes:
            finish_score += 5
        if product.finish_flavors and len(product.finish_flavors) >= 2:
            finish_score += 3
        if product.finish_length:
            finish_score += 2
        score += min(finish_score, 10)

        # Enrichment (20 points) - check JSON arrays
        images = product.images or []
        ratings = product.ratings or []
        awards = product.awards or []

        if product.best_price:
            score += 5
        if images and len(images) > 0:
            score += 5
        if ratings and len(ratings) > 0:
            score += 5
        if awards and len(awards) > 0:
            score += 5

        # Verification bonus (10 points)
        if product.source_count >= 2:
            score += 5
        if product.source_count >= 3:
            score += 5

        product.completeness_score = min(score, 100)
        updated_fields.append("completeness_score")

        # Determine final status based on score and palate data
        if product.status not in ("rejected", "merged"):
            if not has_palate:
                if score >= 30:
                    product.status = "partial"
                else:
                    product.status = "incomplete"
            else:
                if score >= 80:
                    product.status = "verified"
                elif score >= 60:
                    product.status = "complete"
                elif score >= 30:
                    product.status = "partial"
                else:
                    product.status = "incomplete"
            updated_fields.append("status")

        if updated_fields:
            product.save(update_fields=list(set(updated_fields)))


def reverse_migration(apps, schema_editor):
    """
    Reverse migration - restore legacy status values.
    Note: This doesn't restore JSON data as it's still present.
    """
    DiscoveredProduct = apps.get_model("crawler", "DiscoveredProduct")

    # Map new status back to legacy (best effort)
    reverse_mapping = {
        "incomplete": "pending",
        "partial": "pending",
        "complete": "approved",
        "verified": "approved",
        # merged stays as merged
    }

    for product in DiscoveredProduct.objects.filter(
        status__in=["incomplete", "partial", "complete", "verified"]
    ):
        product.status = reverse_mapping.get(product.status, product.status)
        product.save(update_fields=["status"])


class Migration(migrations.Migration):
    dependencies = [
        ("crawler", "0033_unified_pipeline_fields"),
    ]

    operations = [
        migrations.RunPython(migrate_json_to_columns, reverse_migration),
    ]
