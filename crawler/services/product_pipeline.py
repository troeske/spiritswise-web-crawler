"""
Unified Product Pipeline Phase 9: Product Pipeline Service

This module provides the unified product pipeline for processing URLs and
award pages, integrating AI extraction, completeness scoring, status
determination, and database persistence.

The pipeline ensures:
1. Consistent extraction via AI extractor
2. Completeness scoring with tasting profile weighting (40%)
3. Status determination requiring palate for COMPLETE/VERIFIED
4. Proper brand resolution and deduplication
5. Database persistence with all extracted fields

Usage:
    pipeline = UnifiedProductPipeline()
    result = await pipeline.process_url(url, context)
    if result.success:
        print(f"Saved product {result.product_id} with status {result.status}")
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    """Result from the unified product pipeline."""

    success: bool
    product_id: Optional[uuid.UUID]
    status: str
    completeness_score: int
    error: Optional[str] = None
    extracted_data: Dict[str, Any] = field(default_factory=dict)


class UnifiedProductPipeline:
    """
    Unified product pipeline for URL and award page processing.

    Integrates:
    - AI extraction for structured data extraction
    - Completeness scoring with 40% tasting profile weight
    - Status determination (requires palate for COMPLETE)
    - Brand resolution
    - Deduplication
    - Database persistence
    """

    # Scoring weights matching the spec
    MAX_PALATE_SCORE = 20
    MAX_NOSE_SCORE = 10
    MAX_FINISH_SCORE = 10
    MAX_TASTING_SCORE = 40

    def __init__(
        self,
        ai_extractor=None,
        smart_crawler=None,
    ):
        """
        Initialize the unified product pipeline.

        Args:
            ai_extractor: AI extractor for extraction (created if not provided)
            smart_crawler: Smart crawler for fetching (created if not provided)
        """
        if ai_extractor is None:
            from crawler.discovery.extractors.ai_extractor import AIExtractor
            ai_extractor = AIExtractor()
        if smart_crawler is None:
            from crawler.services.smart_crawler import SmartCrawler
            from crawler.services.scrapingbee_client import ScrapingBeeClient
            from crawler.services.ai_client import AIEnhancementClient
            scrapingbee = ScrapingBeeClient()
            ai_client = AIEnhancementClient()
            smart_crawler = SmartCrawler(scrapingbee, ai_client)

        self.ai_extractor = ai_extractor
        self.smart_crawler = smart_crawler

    async def process_url(
        self,
        url: str,
        context: Dict[str, Any],
    ) -> PipelineResult:
        """
        Process a URL through the unified pipeline.

        Steps:
        1. Extract data using AI extractor
        2. Resolve brand
        3. Calculate completeness score
        4. Determine status
        5. Save to database

        Args:
            url: URL to process
            context: Context dict with source, year, product_type_hint, etc.

        Returns:
            PipelineResult with success status, product ID, and metadata
        """
        try:
            # Step 1: Extract data using AI extractor
            extracted_data = await self.ai_extractor.extract(url, context)

            # Handle extraction errors
            if not extracted_data or extracted_data.get('error'):
                error_msg = extracted_data.get('error', 'Extraction returned empty') if extracted_data else 'Extraction failed'
                return PipelineResult(
                    success=False,
                    product_id=None,
                    status='incomplete',
                    completeness_score=0,
                    error=str(error_msg),
                    extracted_data=extracted_data or {},
                )

            # Step 2: Validate minimum required data
            if not extracted_data.get('name'):
                return PipelineResult(
                    success=False,
                    product_id=None,
                    status='incomplete',
                    completeness_score=0,
                    error='No product name extracted',
                    extracted_data=extracted_data,
                )

            # Step 3: Resolve brand
            brand = await self._resolve_brand(extracted_data.get('brand'))

            # Step 4: Determine product type
            product_type = self._determine_product_type(extracted_data, context)

            # Step 5: Calculate completeness score
            completeness_score = self._calculate_completeness(extracted_data)

            # Step 6: Determine status
            status = self._determine_status(extracted_data, completeness_score)

            # Step 7: Save to database
            product = await self._save_product(
                url=url,
                extracted_data=extracted_data,
                brand=brand,
                product_type=product_type,
                completeness_score=completeness_score,
                status=status,
                context=context,
            )

            return PipelineResult(
                success=True,
                product_id=product.id,
                status=status,
                completeness_score=completeness_score,
                error=None,
                extracted_data=extracted_data,
            )

        except Exception as e:
            logger.error(f"Pipeline error processing {url}: {e}")
            return PipelineResult(
                success=False,
                product_id=None,
                status='incomplete',
                completeness_score=0,
                error=str(e),
                extracted_data={},
            )

    async def process_award_page(
        self,
        url: str,
        award_context: Dict[str, Any],
    ) -> PipelineResult:
        """
        Process an award page through the unified pipeline.

        Similar to process_url but adds award data to the product.

        Args:
            url: Award page URL to process
            award_context: Context with source, year, medal_hint, etc.

        Returns:
            PipelineResult with success status, product ID, and metadata
        """
        try:
            # Extract data using AI extractor with award context
            extracted_data = await self.ai_extractor.extract(url, award_context)

            # Handle extraction errors
            if not extracted_data or extracted_data.get('error'):
                error_msg = extracted_data.get('error', 'Extraction returned empty') if extracted_data else 'Extraction failed'
                return PipelineResult(
                    success=False,
                    product_id=None,
                    status='incomplete',
                    completeness_score=0,
                    error=str(error_msg),
                    extracted_data=extracted_data or {},
                )

            # Validate minimum required data
            if not extracted_data.get('name'):
                return PipelineResult(
                    success=False,
                    product_id=None,
                    status='incomplete',
                    completeness_score=0,
                    error='No product name extracted',
                    extracted_data=extracted_data,
                )

            # Resolve brand
            brand = await self._resolve_brand(extracted_data.get('brand'))

            # Determine product type
            product_type = self._determine_product_type(extracted_data, award_context)

            # Calculate completeness score
            completeness_score = self._calculate_completeness(extracted_data)

            # Determine status
            status = self._determine_status(extracted_data, completeness_score)

            # Prepare award data
            award_data = self._prepare_award_data(extracted_data, award_context)

            # Save to database with award data
            product = await self._save_product(
                url=url,
                extracted_data=extracted_data,
                brand=brand,
                product_type=product_type,
                completeness_score=completeness_score,
                status=status,
                context=award_context,
                award_data=award_data,
            )

            return PipelineResult(
                success=True,
                product_id=product.id,
                status=status,
                completeness_score=completeness_score,
                error=None,
                extracted_data=extracted_data,
            )

        except Exception as e:
            logger.error(f"Pipeline error processing award page {url}: {e}")
            return PipelineResult(
                success=False,
                product_id=None,
                status='incomplete',
                completeness_score=0,
                error=str(e),
                extracted_data={},
            )

    def _calculate_completeness(self, extracted_data: Dict[str, Any]) -> int:
        """
        Calculate completeness score for extracted data.

        Scoring breakdown:
        - Identification: 15 points (name + brand)
        - Basic info: 15 points (type + ABV + description)
        - Tasting profile: 40 points (palate 20, nose 10, finish 10)
        - Enrichment: 20 points (price, images, ratings, awards)
        - Verification bonus: 10 points (multi-source)

        Args:
            extracted_data: Extracted product data dict

        Returns:
            Completeness score (0-100)
        """
        score = 0

        # IDENTIFICATION (15 points max)
        if extracted_data.get('name'):
            score += 10
        if extracted_data.get('brand'):
            score += 5

        # BASIC PRODUCT INFO (15 points max)
        if extracted_data.get('product_type'):
            score += 5
        if extracted_data.get('abv'):
            score += 5
        if extracted_data.get('description'):
            score += 5

        # TASTING PROFILE (40 points max)
        score += self._calculate_palate_score(extracted_data)
        score += self._calculate_nose_score(extracted_data)
        score += self._calculate_finish_score(extracted_data)

        # ENRICHMENT DATA (20 points max)
        if extracted_data.get('best_price') or extracted_data.get('price'):
            score += 5
        if extracted_data.get('images'):
            score += 5
        if extracted_data.get('ratings'):
            score += 5
        if extracted_data.get('awards'):
            score += 5

        # VERIFICATION BONUS (10 points max)
        source_count = extracted_data.get('source_count', 1)
        if source_count >= 2:
            score += 5
        if source_count >= 3:
            score += 5

        return min(score, 100)

    def _calculate_palate_score(self, extracted_data: Dict[str, Any]) -> int:
        """
        Calculate palate score (max 20 points).

        Breakdown:
        - 10 points for palate_flavors with 2+ items
        - 5 points for palate_description OR initial_taste
        - 3 points for mid_palate_evolution
        - 2 points for mouthfeel
        """
        score = 0

        # Palate flavors (10 points for 2+ items)
        palate_flavors = extracted_data.get('palate_flavors', [])
        if palate_flavors and len(palate_flavors) >= 2:
            score += 10

        # Palate description or initial taste (5 points)
        if extracted_data.get('palate_description') or extracted_data.get('initial_taste'):
            score += 5

        # Mid-palate evolution (3 points)
        if extracted_data.get('mid_palate_evolution'):
            score += 3

        # Mouthfeel (2 points)
        if extracted_data.get('mouthfeel'):
            score += 2

        return min(score, self.MAX_PALATE_SCORE)

    def _calculate_nose_score(self, extracted_data: Dict[str, Any]) -> int:
        """
        Calculate nose/aroma score (max 10 points).

        Breakdown:
        - 5 points for nose_description
        - 5 points for primary_aromas with 2+ items
        """
        score = 0

        # Nose description (5 points)
        if extracted_data.get('nose_description'):
            score += 5

        # Primary aromas (5 points for 2+ items)
        primary_aromas = extracted_data.get('primary_aromas', [])
        if primary_aromas and len(primary_aromas) >= 2:
            score += 5

        return min(score, self.MAX_NOSE_SCORE)

    def _calculate_finish_score(self, extracted_data: Dict[str, Any]) -> int:
        """
        Calculate finish score (max 10 points).

        Breakdown:
        - 5 points for finish_description
        - 3 points for finish_flavors with 2+ items
        - 2 points for finish_length
        """
        score = 0

        # Finish description (5 points)
        if extracted_data.get('finish_description') or extracted_data.get('final_notes'):
            score += 5

        # Finish flavors (3 points for 2+ items)
        finish_flavors = extracted_data.get('finish_flavors', [])
        if finish_flavors and len(finish_flavors) >= 2:
            score += 3

        # Finish length (2 points)
        if extracted_data.get('finish_length'):
            score += 2

        return min(score, self.MAX_FINISH_SCORE)

    def _has_palate_data(self, extracted_data: Dict[str, Any]) -> bool:
        """
        Check if product has mandatory palate tasting data.

        A product has palate data if ANY of:
        - palate_flavors has 2+ items
        - palate_description is non-empty
        - initial_taste is non-empty

        This is REQUIRED for a product to reach COMPLETE or VERIFIED status.
        """
        # Check palate_flavors (need 2+ items)
        palate_flavors = extracted_data.get('palate_flavors', [])
        if palate_flavors and len(palate_flavors) >= 2:
            return True

        # Check palate_description
        if extracted_data.get('palate_description'):
            return True

        # Check initial_taste
        if extracted_data.get('initial_taste'):
            return True

        return False

    def _determine_status(
        self,
        extracted_data: Dict[str, Any],
        completeness_score: int,
    ) -> str:
        """
        Determine product status based on completeness and tasting data.

        Status Model:
        - INCOMPLETE: Score 0-29, or missing palate
        - PARTIAL: Score 30-59, or has some data but no palate
        - COMPLETE: Score 60-79 AND has palate data
        - VERIFIED: Score 80-100 AND has palate data AND source_count >= 2

        Key rule: COMPLETE/VERIFIED requires palate tasting profile.
        """
        has_palate = self._has_palate_data(extracted_data)
        source_count = extracted_data.get('source_count', 1)

        # Cannot be COMPLETE or VERIFIED without palate data
        if not has_palate:
            if completeness_score >= 30:
                return 'partial'
            return 'incomplete'

        # With palate data, status based on score and source_count
        if completeness_score >= 80 and source_count >= 2:
            return 'verified'
        elif completeness_score >= 60:
            return 'complete'
        elif completeness_score >= 30:
            return 'partial'
        else:
            return 'incomplete'

    def _determine_product_type(
        self,
        extracted_data: Dict[str, Any],
        context: Dict[str, Any],
    ) -> str:
        """
        Determine product type from extracted data or context.
        """
        # Prefer extracted product type
        product_type = extracted_data.get('product_type')
        if product_type:
            return product_type

        # Fall back to context hint
        product_type_hint = context.get('product_type_hint')
        if product_type_hint:
            return product_type_hint

        # Default to whiskey
        return 'whiskey'

    async def _resolve_brand(self, brand_name: Optional[str]):
        """
        Resolve or create brand by name.

        Args:
            brand_name: Brand name to resolve

        Returns:
            DiscoveredBrand instance or None
        """
        if not brand_name:
            return None

        from crawler.models import DiscoveredBrand

        @sync_to_async
        def _get_or_create_brand():
            # Try to find existing brand (case-insensitive)
            brand = DiscoveredBrand.objects.filter(name__iexact=brand_name).first()
            if brand:
                return brand

            # Create new brand
            brand = DiscoveredBrand.objects.create(name=brand_name)
            return brand

        return await _get_or_create_brand()

    def _prepare_award_data(
        self,
        extracted_data: Dict[str, Any],
        award_context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Prepare award data from extracted data and context.
        """
        award_data = {
            'competition': award_context.get('source', 'Unknown'),
            'year': award_context.get('year'),
            'medal': extracted_data.get('medal') or award_context.get('medal_hint'),
            'score': extracted_data.get('score') or award_context.get('score_hint'),
        }

        # Clean up None values
        return {k: v for k, v in award_data.items() if v is not None}

    async def _save_product(
        self,
        url: str,
        extracted_data: Dict[str, Any],
        brand,
        product_type: str,
        completeness_score: int,
        status: str,
        context: Dict[str, Any],
        award_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Save product to database.

        Creates a new DiscoveredProduct with all extracted fields populated.
        """
        from crawler.models import DiscoveredProduct, DiscoverySource
        import hashlib

        # Generate fingerprint for deduplication
        fingerprint = self._compute_fingerprint(extracted_data, product_type)

        @sync_to_async
        def _find_existing():
            return DiscoveredProduct.objects.filter(fingerprint=fingerprint).first()

        existing = await _find_existing()
        if existing:
            # Update existing product
            return await self._update_existing_product(
                existing,
                extracted_data,
                brand,
                completeness_score,
                status,
                award_data,
            )

        # Determine discovery source
        source_name = context.get('source', 'direct')
        if source_name in ['iwsc', 'dwwa', 'sfwsc', 'wwa']:
            discovery_source = DiscoverySource.COMPETITION
        elif source_name == 'search':
            discovery_source = DiscoverySource.SEARCH
        else:
            discovery_source = DiscoverySource.DIRECT

        @sync_to_async
        def _create_product():
            # Create new product with individual fields (not extracted_data JSONField)
            product = DiscoveredProduct(
                name=extracted_data.get('name', ''),
                brand=brand,
                source_url=url,
                product_type=product_type,
                fingerprint=fingerprint,
                status=status,
                completeness_score=completeness_score,
                discovery_source=discovery_source,
                raw_content='',  # Not storing raw content in pipeline
                raw_content_hash=hashlib.sha256(url.encode()).hexdigest(),
            )

            # Populate all individual fields from extracted data
            self._populate_product_fields(product, extracted_data)

            # Add award if present
            if award_data:
                product.awards = [award_data]

            product.save()
            return product

        return await _create_product()

    async def _update_existing_product(
        self,
        product,
        extracted_data: Dict[str, Any],
        brand,
        completeness_score: int,
        status: str,
        award_data: Optional[Dict[str, Any]] = None,
    ):
        """
        Update an existing product with new data.

        Merges new data without overwriting existing non-empty fields
        unless the new data is more complete.
        """
        @sync_to_async
        def _update():
            # Update brand if not set
            if not product.brand and brand:
                product.brand = brand

            # Update completeness score if higher
            if completeness_score > (product.completeness_score or 0):
                product.completeness_score = completeness_score
                product.status = status

            # Merge extracted data
            self._merge_product_fields(product, extracted_data)

            # Add award if present and not duplicate
            if award_data:
                awards = product.awards or []
                # Check for duplicate award
                is_duplicate = any(
                    a.get('competition') == award_data.get('competition') and
                    a.get('year') == award_data.get('year')
                    for a in awards
                )
                if not is_duplicate:
                    awards.append(award_data)
                    product.awards = awards

            # Increment source count
            product.source_count = (product.source_count or 1) + 1

            product.save()
            return product

        return await _update()

    def _populate_product_fields(self, product, extracted_data: Dict[str, Any]):
        """
        Populate product fields from extracted data.
        """
        # Basic fields
        if extracted_data.get('abv'):
            try:
                product.abv = float(extracted_data['abv'])
            except (ValueError, TypeError):
                pass
        if extracted_data.get('age_statement'):
            try:
                product.age_statement = int(extracted_data['age_statement'])
            except (ValueError, TypeError):
                pass
        if extracted_data.get('volume_ml'):
            try:
                product.volume_ml = int(extracted_data['volume_ml'])
            except (ValueError, TypeError):
                pass
        if extracted_data.get('region'):
            product.region = extracted_data['region']
        if extracted_data.get('country'):
            product.country = extracted_data['country']
        if extracted_data.get('category'):
            product.category = extracted_data['category']
        if extracted_data.get('bottler'):
            product.bottler = extracted_data['bottler']

        # Tasting profile - Nose
        if extracted_data.get('nose_description'):
            product.nose_description = extracted_data['nose_description']
        if extracted_data.get('primary_aromas'):
            product.primary_aromas = extracted_data['primary_aromas']
        if extracted_data.get('secondary_aromas'):
            product.secondary_aromas = extracted_data['secondary_aromas']
        if extracted_data.get('aroma_evolution'):
            product.aroma_evolution = extracted_data['aroma_evolution']

        # Tasting profile - Palate
        if extracted_data.get('palate_description'):
            product.palate_description = extracted_data['palate_description']
        if extracted_data.get('palate_flavors'):
            product.palate_flavors = extracted_data['palate_flavors']
        if extracted_data.get('initial_taste'):
            product.initial_taste = extracted_data['initial_taste']
        if extracted_data.get('mid_palate_evolution'):
            product.mid_palate_evolution = extracted_data['mid_palate_evolution']
        if extracted_data.get('mouthfeel'):
            product.mouthfeel = extracted_data['mouthfeel']
        if extracted_data.get('flavor_intensity'):
            product.flavor_intensity = extracted_data['flavor_intensity']
        if extracted_data.get('complexity'):
            product.complexity = extracted_data['complexity']

        # Tasting profile - Finish
        if extracted_data.get('finish_description'):
            product.finish_description = extracted_data['finish_description']
        if extracted_data.get('finish_flavors'):
            product.finish_flavors = extracted_data['finish_flavors']
        if extracted_data.get('finish_length'):
            try:
                product.finish_length = int(extracted_data['finish_length'])
            except (ValueError, TypeError):
                pass
        if extracted_data.get('warmth'):
            product.warmth = extracted_data['warmth']
        if extracted_data.get('dryness'):
            product.dryness = extracted_data['dryness']
        if extracted_data.get('final_notes'):
            product.final_notes = extracted_data['final_notes']

        # Overall assessment
        if extracted_data.get('balance'):
            product.balance = extracted_data['balance']
        if extracted_data.get('overall_complexity'):
            product.overall_complexity = extracted_data['overall_complexity']
        if extracted_data.get('uniqueness'):
            product.uniqueness = extracted_data['uniqueness']
        if extracted_data.get('drinkability'):
            product.drinkability = extracted_data['drinkability']
        if extracted_data.get('experience_level'):
            product.experience_level = extracted_data['experience_level']
        if extracted_data.get('serving_recommendation'):
            product.serving_recommendation = extracted_data['serving_recommendation']
        if extracted_data.get('food_pairings'):
            product.food_pairings = extracted_data['food_pairings']

        # Appearance
        if extracted_data.get('color_description'):
            product.color_description = extracted_data['color_description']
        if extracted_data.get('color_intensity'):
            product.color_intensity = extracted_data['color_intensity']
        if extracted_data.get('clarity'):
            product.clarity = extracted_data['clarity']
        if extracted_data.get('viscosity'):
            product.viscosity = extracted_data['viscosity']

        # Cask information
        if extracted_data.get('primary_cask'):
            product.primary_cask = extracted_data['primary_cask']
        if extracted_data.get('finishing_cask'):
            product.finishing_cask = extracted_data['finishing_cask']
        if extracted_data.get('wood_type'):
            product.wood_type = extracted_data['wood_type']
        if extracted_data.get('cask_treatment'):
            product.cask_treatment = extracted_data['cask_treatment']
        if extracted_data.get('maturation_notes'):
            product.maturation_notes = extracted_data['maturation_notes']

        # Pricing
        if extracted_data.get('price') or extracted_data.get('best_price'):
            try:
                price = extracted_data.get('price') or extracted_data.get('best_price')
                from decimal import Decimal
                product.best_price = Decimal(str(price))
            except (ValueError, TypeError):
                pass

        # Images
        if extracted_data.get('images'):
            product.images = extracted_data['images']

        # Ratings
        if extracted_data.get('ratings'):
            product.ratings = extracted_data['ratings']

    def _merge_product_fields(self, product, extracted_data: Dict[str, Any]):
        """
        Merge extracted data into existing product, only filling empty fields.
        """
        # Only update fields that are currently empty
        field_mapping = {
            'abv': 'abv',
            'region': 'region',
            'country': 'country',
            'category': 'category',
            'nose_description': 'nose_description',
            'palate_description': 'palate_description',
            'finish_description': 'finish_description',
            'color_description': 'color_description',
            'maturation_notes': 'maturation_notes',
            'food_pairings': 'food_pairings',
        }

        for data_key, model_field in field_mapping.items():
            current_value = getattr(product, model_field, None)
            new_value = extracted_data.get(data_key)
            if not current_value and new_value:
                setattr(product, model_field, new_value)

        # Merge list fields
        list_fields = [
            'primary_aromas', 'secondary_aromas', 'palate_flavors',
            'finish_flavors', 'primary_cask', 'finishing_cask',
        ]
        for field_name in list_fields:
            current_value = getattr(product, field_name, None) or []
            new_value = extracted_data.get(field_name, [])
            if new_value:
                # Merge lists without duplicates
                merged = list(set(current_value) | set(new_value))
                setattr(product, field_name, merged)

    def _compute_fingerprint(
        self,
        extracted_data: Dict[str, Any],
        product_type: str,
    ) -> str:
        """
        Compute fingerprint for deduplication based on key fields.
        """
        import hashlib
        import json

        key_fields = {
            'name': str(extracted_data.get('name', '')).lower().strip(),
            'brand': str(extracted_data.get('brand', '')).lower().strip(),
            'product_type': product_type,
            'volume_ml': extracted_data.get('volume_ml'),
            'abv': extracted_data.get('abv'),
        }

        # Add type-specific fields
        if product_type == 'whiskey':
            key_fields['age_statement'] = extracted_data.get('age_statement')
            key_fields['distillery'] = str(extracted_data.get('distillery', '')).lower()
        elif product_type == 'port_wine':
            key_fields['style'] = str(extracted_data.get('style', '')).lower()
            key_fields['harvest_year'] = extracted_data.get('harvest_year')

        fingerprint_str = json.dumps(key_fields, sort_keys=True)
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()
