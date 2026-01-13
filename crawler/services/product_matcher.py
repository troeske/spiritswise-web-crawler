"""
ProductMatcher Service for Single Product Enrichment.

Task 2.1: Shared duplicate detection across all discovery flows.

Provides a unified interface for finding existing products with:
1. GTIN matching (highest confidence = 1.0)
2. Fingerprint matching (confidence = 0.95)
3. Fuzzy name matching with brand filter (confidence = 0.85+)

Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 4.1, 6.2
"""

import logging
from typing import Any, Dict, Optional, Tuple
from uuid import UUID

from django.db.models import Q

from django.utils.text import slugify

from crawler.models import DiscoveredProduct, DiscoveredBrand

logger = logging.getLogger(__name__)


class ProductMatcher:
    """
    Unified product matching service for all discovery flows.

    Wraps duplicate detection with a cleaner interface that returns:
    - The matched product (or None)
    - The match method used (gtin, fingerprint, fuzzy_name, none)
    - A confidence score (0.0-1.0)

    Spec Reference: SINGLE_PRODUCT_ENRICHMENT_SPEC.md Section 4.1
    """

    # Confidence thresholds
    GTIN_CONFIDENCE = 1.0
    FINGERPRINT_CONFIDENCE = 0.95
    FUZZY_NAME_BASE_CONFIDENCE = 0.70
    BRAND_MATCH_BOOST = 0.15  # Added when brand matches exactly
    MIN_MATCH_CONFIDENCE = 0.85  # Minimum to consider a match

    def __init__(self):
        """Initialize ProductMatcher."""
        pass

    async def find_match(
        self,
        extracted_data: Dict[str, Any],
        product_type: str,
    ) -> Tuple[Optional[DiscoveredProduct], str, float]:
        """
        Find existing product matching extracted data.

        Uses a 3-level matching pipeline:
        1. GTIN match (if available) - highest confidence
        2. Fingerprint match - high confidence
        3. Fuzzy name/brand match - requires threshold

        Args:
            extracted_data: Dict with product data (name, brand, gtin, etc.)
            product_type: Product type (whiskey, port_wine, etc.)

        Returns:
            Tuple of:
            - DiscoveredProduct or None
            - match_method: "gtin" | "fingerprint" | "fuzzy_name" | "none"
            - confidence: 0.0-1.0
        """
        # Level 1: GTIN match (highest confidence)
        gtin = extracted_data.get("gtin")
        if gtin:
            product = await self._match_by_gtin(gtin, product_type)
            if product:
                logger.info(f"GTIN match found: {product.id} for GTIN {gtin}")
                return product, "gtin", self.GTIN_CONFIDENCE

        # Level 2: Fingerprint match
        fingerprint = self._compute_fingerprint(extracted_data)
        if fingerprint:
            product = await self._match_by_fingerprint(fingerprint, product_type)
            if product:
                logger.info(f"Fingerprint match found: {product.id}")
                return product, "fingerprint", self.FINGERPRINT_CONFIDENCE

        # Level 3: Fuzzy name match with brand filter
        name = extracted_data.get("name")
        brand = extracted_data.get("brand")
        if name:
            product, confidence = await self._match_by_fuzzy_name(
                name, brand, product_type
            )
            if product and confidence >= self.MIN_MATCH_CONFIDENCE:
                logger.info(
                    f"Fuzzy name match found: {product.id} "
                    f"(confidence={confidence:.2f})"
                )
                return product, "fuzzy_name", confidence

        logger.debug(f"No match found for {extracted_data.get('name', 'unknown')}")
        return None, "none", 0.0

    async def find_or_create(
        self,
        extracted_data: Dict[str, Any],
        product_type: str,
        source_url: str,
    ) -> Tuple[DiscoveredProduct, bool]:
        """
        Find existing product or create new one.

        Convenience method that combines matching and creation.

        Args:
            extracted_data: Dict with product data
            product_type: Product type
            source_url: URL where product was found

        Returns:
            Tuple of:
            - DiscoveredProduct (existing or newly created)
            - is_new: True if created, False if existing
        """
        product, match_method, confidence = await self.find_match(
            extracted_data, product_type
        )

        if product:
            return product, False

        # Create new product
        product = await self._create_product(extracted_data, product_type, source_url)
        return product, True

    async def _match_by_gtin(
        self, gtin: str, product_type: str
    ) -> Optional[DiscoveredProduct]:
        """Match product by GTIN (exact match)."""
        try:
            return await DiscoveredProduct.objects.filter(
                gtin=gtin,
                product_type=product_type,
            ).afirst()
        except Exception as e:
            logger.warning(f"GTIN match error: {e}")
            return None

    async def _match_by_fingerprint(
        self, fingerprint: str, product_type: str
    ) -> Optional[DiscoveredProduct]:
        """Match product by fingerprint hash."""
        try:
            return await DiscoveredProduct.objects.filter(
                fingerprint=fingerprint,
                product_type=product_type,
            ).afirst()
        except Exception as e:
            logger.warning(f"Fingerprint match error: {e}")
            return None

    async def _match_by_fuzzy_name(
        self,
        name: str,
        brand: Optional[str],
        product_type: str,
    ) -> Tuple[Optional[DiscoveredProduct], float]:
        """
        Match product by fuzzy name with brand filter.

        Matching strategy:
        1. Filter by product_type
        2. If brand provided, filter by exact brand match (case-insensitive)
        3. Search for name containing first significant word

        Confidence calculation:
        - Base confidence for name match: 0.70
        - Brand match boost: +0.15
        - Name similarity boost: up to +0.15 based on match quality

        Returns:
            Tuple of (product, confidence)
        """
        try:
            # Get first significant word from name (skip articles)
            first_word = self._get_first_significant_word(name)
            if not first_word or len(first_word) < 3:
                return None, 0.0

            # Search for products - wrap entire query in sync_to_async
            from asgiref.sync import sync_to_async

            @sync_to_async
            def get_candidates():
                # Build query inside sync context
                queryset = DiscoveredProduct.objects.filter(product_type=product_type)
                if brand:
                    queryset = queryset.filter(brand__name__iexact=brand)
                return list(
                    queryset.filter(name__icontains=first_word)
                    .select_related('brand')
                    .order_by('-discovered_at')[:10]
                )

            candidates = await get_candidates()

            if not candidates:
                return None, 0.0

            # Find best match
            best_match = None
            best_confidence = 0.0

            for candidate in candidates:
                confidence = self._calculate_match_confidence(
                    name, brand, candidate.name, candidate.brand
                )
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_match = candidate

            return best_match, best_confidence

        except Exception as e:
            logger.warning(f"Fuzzy name match error: {e}")
            return None, 0.0

    def _compute_fingerprint(self, data: Dict[str, Any]) -> Optional[str]:
        """
        Compute fingerprint hash for product data.

        Fingerprint is based on normalized name + brand + product_type.
        """
        import hashlib

        name = data.get("name", "").lower().strip()
        brand = data.get("brand", "").lower().strip()

        if not name:
            return None

        # Create fingerprint from normalized fields
        fingerprint_str = f"{name}|{brand}"
        return hashlib.sha256(fingerprint_str.encode()).hexdigest()[:32]

    def _get_first_significant_word(self, name: str) -> Optional[str]:
        """Get first significant word from product name (skip articles)."""
        if not name:
            return None

        # Words to skip
        skip_words = {"the", "a", "an", "le", "la", "el", "los", "las"}

        words = name.lower().split()
        for word in words:
            # Clean word of punctuation
            clean_word = "".join(c for c in word if c.isalnum())
            if clean_word and clean_word not in skip_words:
                return clean_word

        return words[0] if words else None

    def _calculate_match_confidence(
        self,
        search_name: str,
        search_brand: Optional[str],
        candidate_name: str,
        candidate_brand: Any,  # Can be DiscoveredBrand object or string
    ) -> float:
        """
        Calculate match confidence between search and candidate.

        Factors:
        - Name similarity (Jaccard coefficient of words)
        - Brand exact match bonus
        """
        confidence = self.FUZZY_NAME_BASE_CONFIDENCE

        # Extract brand name if it's a DiscoveredBrand object
        candidate_brand_name = None
        if candidate_brand:
            if hasattr(candidate_brand, 'name'):
                candidate_brand_name = candidate_brand.name
            else:
                candidate_brand_name = str(candidate_brand)

        # Brand match bonus
        if search_brand and candidate_brand_name:
            if search_brand.lower().strip() == candidate_brand_name.lower().strip():
                confidence += self.BRAND_MATCH_BOOST

        # Name similarity bonus (Jaccard coefficient)
        search_words = set(search_name.lower().split())
        candidate_words = set(candidate_name.lower().split())

        if search_words and candidate_words:
            intersection = len(search_words & candidate_words)
            union = len(search_words | candidate_words)
            similarity = intersection / union if union > 0 else 0
            confidence += similarity * 0.15  # Up to 0.15 bonus

        return min(confidence, 1.0)

    async def _create_product(
        self,
        extracted_data: Dict[str, Any],
        product_type: str,
        source_url: str,
    ) -> DiscoveredProduct:
        """Create new DiscoveredProduct from extracted data."""
        fingerprint = self._compute_fingerprint(extracted_data)

        # Get or create brand if name provided
        brand = None
        brand_name = extracted_data.get("brand", "")
        if brand_name:
            brand = await self._get_or_create_brand(brand_name)

        product = await DiscoveredProduct.objects.acreate(
            name=extracted_data.get("name", "Unknown"),
            brand=brand,
            product_type=product_type,
            gtin=extracted_data.get("gtin"),
            fingerprint=fingerprint,
            source_url=source_url,
        )

        logger.info(f"Created new product: {product.id} - {product.name}")
        return product

    async def _get_or_create_brand(self, name: str) -> DiscoveredBrand:
        """Get or create a DiscoveredBrand by name."""
        # Try to find existing brand (case-insensitive)
        brand = await DiscoveredBrand.objects.filter(name__iexact=name).afirst()
        if brand:
            return brand

        # Create new brand with unique slug
        base_slug = slugify(name)
        slug = base_slug
        counter = 1

        # Ensure unique slug
        while await DiscoveredBrand.objects.filter(slug=slug).aexists():
            slug = f"{base_slug}-{counter}"
            counter += 1

        brand = await DiscoveredBrand.objects.acreate(name=name, slug=slug)
        logger.info(f"Created new brand: {brand.id} - {brand.name}")
        return brand


# Singleton instance
_product_matcher: Optional[ProductMatcher] = None


def get_product_matcher() -> ProductMatcher:
    """Get singleton ProductMatcher instance."""
    global _product_matcher
    if _product_matcher is None:
        _product_matcher = ProductMatcher()
    return _product_matcher


def reset_product_matcher() -> None:
    """Reset singleton (for testing)."""
    global _product_matcher
    _product_matcher = None
