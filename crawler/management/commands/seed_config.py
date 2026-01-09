"""
Management command to seed V2 configuration data for product types.

Seeds ProductTypeConfig, FieldDefinition, QualityGateConfig, and EnrichmentConfig
from JSON fixture files.

Usage:
    python manage.py seed_config                        # Seed all product types
    python manage.py seed_config --product-type=whiskey # Seed whiskey only
    python manage.py seed_config --product-type=all --clear  # Clear and reseed all
    python manage.py seed_config --dry-run              # Preview without changes

Spec Reference: CRAWLER_AI_SERVICE_ARCHITECTURE_V2.md Sections 2.5, 5.1, 5.2
"""

import json
import uuid
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from crawler.models import (
    ProductTypeConfig,
    FieldDefinition,
    QualityGateConfig,
    EnrichmentConfig,
)


class Command(BaseCommand):
    help = "Seed V2 configuration data for whiskey and port wine"

    def add_arguments(self, parser):
        parser.add_argument(
            "--product-type",
            type=str,
            default="all",
            choices=["whiskey", "port_wine", "all"],
            help="Seed specific type: whiskey, port_wine, or all (default: all)",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing config before seeding",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be seeded without making changes",
        )
        parser.add_argument(
            "--skip-existing",
            action="store_true",
            default=True,
            help="Skip records that already exist (default: True)",
        )

    def handle(self, *args, **options):
        product_type = options["product_type"]
        clear = options["clear"]
        dry_run = options["dry_run"]
        skip_existing = options["skip_existing"]

        fixtures_dir = Path(__file__).parent.parent.parent / "fixtures"

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN - No changes will be made"))

        # Determine which types to seed
        types_to_seed = []
        if product_type == "all":
            types_to_seed = ["whiskey", "port_wine"]
        else:
            types_to_seed = [product_type]

        # Clear if requested
        if clear and not dry_run:
            self._clear_existing_config(types_to_seed)

        # Always seed base fields first
        self._seed_base_fields(fixtures_dir, dry_run, skip_existing)

        # Seed each product type
        for ptype in types_to_seed:
            self._seed_product_type(ptype, fixtures_dir, dry_run, skip_existing)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Seeding complete!"))

    def _clear_existing_config(self, types_to_seed):
        """Clear existing configuration for specified product types."""
        self.stdout.write(self.style.WARNING(f"Clearing existing config for: {types_to_seed}"))

        # Clear base fields (product_type_config=null)
        base_count = FieldDefinition.objects.filter(product_type_config__isnull=True).count()
        FieldDefinition.objects.filter(product_type_config__isnull=True).delete()
        self.stdout.write(f"  Deleted {base_count} base field definitions")

        # Clear type-specific configs
        for ptype in types_to_seed:
            try:
                config = ProductTypeConfig.objects.get(product_type=ptype)
                # Cascade delete will handle related FieldDefinitions, QualityGateConfig, EnrichmentConfig
                config.delete()
                self.stdout.write(f"  Deleted {ptype} configuration and related records")
            except ProductTypeConfig.DoesNotExist:
                self.stdout.write(f"  No existing {ptype} configuration found")

    def _seed_base_fields(self, fixtures_dir, dry_run, skip_existing):
        """Seed shared/base field definitions from base_fields.json."""
        base_fields_file = fixtures_dir / "base_fields.json"

        if not base_fields_file.exists():
            raise CommandError(f"Base fields fixture not found: {base_fields_file}")

        with open(base_fields_file, "r", encoding="utf-8") as f:
            base_fields_data = json.load(f)

        self.stdout.write(f"\nSeeding base field definitions from {base_fields_file}")
        created = 0
        skipped = 0

        for field_data in base_fields_data:
            fields = field_data["fields"]
            pk = field_data["pk"]

            # Check if exists
            exists = FieldDefinition.objects.filter(
                product_type_config__isnull=True,
                field_name=fields["field_name"]
            ).exists()

            if exists and skip_existing:
                self.stdout.write(f"  Skipping (exists): {fields['field_name']}")
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(f"  Would create: {fields['field_name']} (base)")
                created += 1
            else:
                try:
                    FieldDefinition.objects.update_or_create(
                        id=uuid.UUID(pk),
                        defaults={
                            "product_type_config": None,
                            "field_name": fields["field_name"],
                            "display_name": fields["display_name"],
                            "field_group": fields["field_group"],
                            "field_type": fields["field_type"],
                            "item_type": fields.get("item_type", ""),
                            "description": fields["description"],
                            "examples": fields.get("examples", []),
                            "allowed_values": fields.get("allowed_values", []),
                            "item_schema": fields.get("item_schema", {}),
                            "target_model": fields["target_model"],
                            "target_field": fields["target_field"],
                            "sort_order": fields.get("sort_order", 0),
                            "is_active": fields.get("is_active", True),
                        }
                    )
                    self.stdout.write(self.style.SUCCESS(f"  Created: {fields['field_name']} (base)"))
                    created += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Error creating {fields['field_name']}: {e}"))

        self.stdout.write(f"  Base fields - Created: {created}, Skipped: {skipped}")

    def _seed_product_type(self, ptype, fixtures_dir, dry_run, skip_existing):
        """Seed configuration for a specific product type."""
        config_file = fixtures_dir / f"{ptype}_config.json"

        if not config_file.exists():
            raise CommandError(f"Config fixture not found: {config_file}")

        with open(config_file, "r", encoding="utf-8") as f:
            config_data = json.load(f)

        self.stdout.write(f"\nSeeding {ptype} configuration from {config_file}")

        # Seed ProductTypeConfig
        product_type_config = self._seed_product_type_config(
            config_data["product_type_config"], dry_run, skip_existing
        )

        if product_type_config or dry_run:
            # Seed QualityGateConfig
            self._seed_quality_gate_config(
                config_data["quality_gate_config"],
                product_type_config,
                dry_run,
                skip_existing
            )

            # Seed FieldDefinitions
            self._seed_field_definitions(
                config_data["field_definitions"],
                product_type_config,
                dry_run,
                skip_existing
            )

            # Seed EnrichmentConfigs
            self._seed_enrichment_configs(
                config_data["enrichment_configs"],
                product_type_config,
                dry_run,
                skip_existing
            )

    def _seed_product_type_config(self, data, dry_run, skip_existing):
        """Seed ProductTypeConfig record."""
        product_type = data["product_type"]

        exists = ProductTypeConfig.objects.filter(product_type=product_type).exists()

        if exists and skip_existing:
            self.stdout.write(f"  Skipping ProductTypeConfig (exists): {product_type}")
            return ProductTypeConfig.objects.get(product_type=product_type)

        if dry_run:
            self.stdout.write(f"  Would create ProductTypeConfig: {product_type}")
            return None

        try:
            config, created = ProductTypeConfig.objects.update_or_create(
                id=uuid.UUID(data["pk"]),
                defaults={
                    "product_type": product_type,
                    "display_name": data["display_name"],
                    "version": data.get("version", "1.0"),
                    "is_active": data.get("is_active", True),
                    "categories": data.get("categories", []),
                    "max_sources_per_product": data.get("max_sources_per_product", 5),
                    "max_serpapi_searches": data.get("max_serpapi_searches", 3),
                    "max_enrichment_time_seconds": data.get("max_enrichment_time_seconds", 120),
                }
            )
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  {action} ProductTypeConfig: {product_type}"))
            return config
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Error creating ProductTypeConfig {product_type}: {e}"))
            return None

    def _seed_quality_gate_config(self, data, product_type_config, dry_run, skip_existing):
        """Seed QualityGateConfig record."""
        if product_type_config is None and not dry_run:
            return

        ptype_name = product_type_config.product_type if product_type_config else "unknown"

        if product_type_config:
            exists = QualityGateConfig.objects.filter(
                product_type_config=product_type_config
            ).exists()

            if exists and skip_existing:
                self.stdout.write(f"  Skipping QualityGateConfig (exists): {ptype_name}")
                return

        if dry_run:
            self.stdout.write(f"  Would create QualityGateConfig: {ptype_name}")
            return

        try:
            config, created = QualityGateConfig.objects.update_or_create(
                id=uuid.UUID(data["pk"]),
                defaults={
                    "product_type_config": product_type_config,
                    "skeleton_required_fields": data.get("skeleton_required_fields", []),
                    "partial_required_fields": data.get("partial_required_fields", []),
                    "partial_any_of_count": data.get("partial_any_of_count", 2),
                    "partial_any_of_fields": data.get("partial_any_of_fields", []),
                    "complete_required_fields": data.get("complete_required_fields", []),
                    "complete_any_of_count": data.get("complete_any_of_count", 2),
                    "complete_any_of_fields": data.get("complete_any_of_fields", []),
                    "enriched_required_fields": data.get("enriched_required_fields", []),
                    "enriched_any_of_count": data.get("enriched_any_of_count", 2),
                    "enriched_any_of_fields": data.get("enriched_any_of_fields", []),
                }
            )
            action = "Created" if created else "Updated"
            self.stdout.write(self.style.SUCCESS(f"  {action} QualityGateConfig: {ptype_name}"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  Error creating QualityGateConfig: {e}"))

    def _seed_field_definitions(self, fields_data, product_type_config, dry_run, skip_existing):
        """Seed type-specific FieldDefinition records."""
        if product_type_config is None and not dry_run:
            return

        ptype_name = product_type_config.product_type if product_type_config else "unknown"
        created = 0
        skipped = 0

        for field_data in fields_data:
            field_name = field_data["field_name"]

            if product_type_config:
                exists = FieldDefinition.objects.filter(
                    product_type_config=product_type_config,
                    field_name=field_name
                ).exists()

                if exists and skip_existing:
                    skipped += 1
                    continue

            if dry_run:
                self.stdout.write(f"  Would create FieldDefinition: {field_name} ({ptype_name})")
                created += 1
            else:
                try:
                    FieldDefinition.objects.update_or_create(
                        id=uuid.UUID(field_data["pk"]),
                        defaults={
                            "product_type_config": product_type_config,
                            "field_name": field_name,
                            "display_name": field_data["display_name"],
                            "field_group": field_data["field_group"],
                            "field_type": field_data["field_type"],
                            "item_type": field_data.get("item_type", ""),
                            "description": field_data["description"],
                            "examples": field_data.get("examples", []),
                            "allowed_values": field_data.get("allowed_values", []),
                            "item_schema": field_data.get("item_schema", {}),
                            "target_model": field_data["target_model"],
                            "target_field": field_data["target_field"],
                            "sort_order": field_data.get("sort_order", 0),
                            "is_active": field_data.get("is_active", True),
                        }
                    )
                    created += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Error creating FieldDefinition {field_name}: {e}"))

        self.stdout.write(f"  FieldDefinitions ({ptype_name}) - Created: {created}, Skipped: {skipped}")

    def _seed_enrichment_configs(self, configs_data, product_type_config, dry_run, skip_existing):
        """Seed EnrichmentConfig records."""
        if product_type_config is None and not dry_run:
            return

        ptype_name = product_type_config.product_type if product_type_config else "unknown"
        created = 0
        skipped = 0

        for config_data in configs_data:
            template_name = config_data["template_name"]

            if product_type_config:
                exists = EnrichmentConfig.objects.filter(
                    product_type_config=product_type_config,
                    template_name=template_name
                ).exists()

                if exists and skip_existing:
                    skipped += 1
                    continue

            if dry_run:
                self.stdout.write(f"  Would create EnrichmentConfig: {template_name} ({ptype_name})")
                created += 1
            else:
                try:
                    EnrichmentConfig.objects.update_or_create(
                        id=uuid.UUID(config_data["pk"]),
                        defaults={
                            "product_type_config": product_type_config,
                            "template_name": template_name,
                            "display_name": config_data["display_name"],
                            "search_template": config_data["search_template"],
                            "target_fields": config_data.get("target_fields", []),
                            "priority": config_data.get("priority", 5),
                            "is_active": config_data.get("is_active", True),
                        }
                    )
                    created += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  Error creating EnrichmentConfig {template_name}: {e}"))

        self.stdout.write(f"  EnrichmentConfigs ({ptype_name}) - Created: {created}, Skipped: {skipped}")
