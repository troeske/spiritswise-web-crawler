"""
Additional models for Web Crawler System.

This file contains the missing models that tests expect.
These will be appended to the main models.py file.
"""

# ============================================================
# Task Group 1: DiscoveredBrand Model and Related Choices
# ============================================================


class WhiskeyTypeChoices(models.TextChoices):
    """
    Task Group 3: Whiskey type choices for WhiskeyDetails.

    Classifies the type of whiskey:
    """
    SCOTCH_SINGLE_MALT = "scotch_single_malt", "Scotch Single Malt"
    SCOTCH_BLEND = "scotch_blend", "Scotch Blend"
    BOURBON = "bourbon", "Bourbon"
    TENNESSEE = "tennessee", "Tennessee"
    RYE = "rye", "Rye"
    IRISH_SINGLE_POT = "irish_single_pot", "Irish Single Pot Still"
    IRISH_SINGLE_MALT = "irish_single_malt", "Irish Single Malt"
    IRISH_BLEND = "irish_blend", "Irish Blend"
    JAPANESE = "japanese", "Japanese"
    CANADIAN = "canadian", "Canadian"
    INDIAN = "indian", "Indian"
    TAIWANESE = "taiwanese", "Taiwanese"
    AUSTRALIAN = "australian", "Australian"
    AMERICAN_SINGLE_MALT = "american_single_malt", "American Single Malt"
    WORLD_WHISKEY = "world_whiskey", "World Whiskey"


class PortStyleChoices(models.TextChoices):
    """
    Task Group 3: Port wine style choices for PortWineDetails.
    """
    RUBY = "ruby", "Ruby"
    TAWNY = "tawny", "Tawny"
    WHITE = "white", "White"
    ROSE = "rose", "Rose"
    LBV = "lbv", "Late Bottled Vintage (LBV)"
    VINTAGE = "vintage", "Vintage"
    COLHEITA = "colheita", "Colheita"
    CRUSTED = "crusted", "Crusted"
    SINGLE_QUINTA = "single_quinta", "Single Quinta"
    GARRAFEIRA = "garrafeira", "Garrafeira"


class MedalChoices(models.TextChoices):
    """
    Task Group 4: Medal choices for awards.
    """
    DOUBLE_GOLD = "double_gold", "Double Gold"
    GOLD = "gold", "Gold"
    SILVER = "silver", "Silver"
    BRONZE = "bronze", "Bronze"
    BEST_IN_CLASS = "best_in_class", "Best in Class"
    CATEGORY_WINNER = "category_winner", "Category Winner"


class ImageTypeChoices(models.TextChoices):
    """
    Task Group 4: Image type choices for ProductImage.
    """
    BOTTLE = "bottle", "Bottle"
    LABEL = "label", "Label"
    PACKAGING = "packaging", "Packaging"
    LIFESTYLE = "lifestyle", "Lifestyle"


class MatchStatusChoices(models.TextChoices):
    """
    Task Group 12: Match status choices for ProductCandidate.
    """
    PENDING = "pending", "Pending"
    MATCHED = "matched", "Matched"
    NEW_PRODUCT = "new_product", "New Product"
    NEEDS_REVIEW = "needs_review", "Needs Review"


class ReleaseStatusChoices(models.TextChoices):
    """
    Task Group 18: Release status choices for NewRelease.
    """
    RUMORED = "rumored", "Rumored"
    ANNOUNCED = "announced", "Announced"
    PRE_ORDER = "pre_order", "Pre-Order"
    RELEASED = "released", "Released"
    CANCELLED = "cancelled", "Cancelled"


class PriceAlertTypeChoices(models.TextChoices):
    """
    Task Group 17: Alert type choices for PriceAlert.
    """
    PRICE_DROP = "price_drop", "Price Drop"
    PRICE_SPIKE = "price_spike", "Price Spike"
    NEW_LOW = "new_low", "New Low"
    BACK_IN_STOCK = "back_in_stock", "Back in Stock"


class PriceTrendChoices(models.TextChoices):
    """
    Task Group 16: Price trend choices.
    """
    RISING = "rising", "Rising"
    STABLE = "stable", "Stable"
    FALLING = "falling", "Falling"


class PeatLevelChoices(models.TextChoices):
    """
    Task Group 3: Peat level choices for WhiskeyDetails.
    """
    UNPEATED = "unpeated", "Unpeated"
    LIGHTLY_PEATED = "lightly_peated", "Lightly Peated"
    MEDIUM_PEATED = "medium_peated", "Medium Peated"
    HEAVILY_PEATED = "heavily_peated", "Heavily Peated"


class DouroSubregionChoices(models.TextChoices):
    """
    Task Group 3: Douro subregion choices for PortWineDetails.
    """
    BAIXO_CORGO = "baixo_corgo", "Baixo Corgo"
    CIMA_CORGO = "cima_corgo", "Cima Corgo"
    DOURO_SUPERIOR = "douro_superior", "Douro Superior"


# Alias for tests that use DiscoverySourceTypeChoices
DiscoverySourceTypeChoices = SourceTypeChoices


# ============================================================
# Task Group 1: DiscoveredBrand Model
# ============================================================


class DiscoveredBrand(models.Model):
    """
    Task Group 1: Brand information discovered during crawling.

    Stores information about brands/distilleries/producers discovered
    during the crawling process.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Identity
    name = models.CharField(
        max_length=200,
        help_text="Brand name",
    )
    slug = models.SlugField(
        max_length=200,
        unique=True,
        blank=True,
        help_text="URL-safe identifier",
    )

    # Location
    country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Country of origin",
    )
    region = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Region within country",
    )
    headquarters_country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Country where headquarters is located",
    )

    # Details
    official_website = models.URLField(
        blank=True,
        null=True,
        help_text="Official brand website",
    )
    founded_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year the brand was founded",
    )

    # Statistics
    product_count = models.IntegerField(
        default=0,
        help_text="Number of products from this brand",
    )
    award_count = models.IntegerField(
        default=0,
        help_text="Total awards won by the brand",
    )
    mention_count = models.IntegerField(
        default=0,
        help_text="Number of source mentions",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "discovered_brand"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["country"]),
        ]
        verbose_name = "Discovered Brand"
        verbose_name_plural = "Discovered Brands"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided."""
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.name)
            self.slug = base_slug
            # Ensure uniqueness
            counter = 1
            while DiscoveredBrand.objects.filter(slug=self.slug).exclude(id=self.id).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


# ============================================================
# Task Group 3: Spirit-Type Extension Models
# ============================================================


class WhiskeyDetails(models.Model):
    """
    Task Group 3: Extended details for whiskey products.

    OneToOne relationship with DiscoveredProduct for whiskey-specific fields.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # OneToOne relationship
    product = models.OneToOneField(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='whiskey_details',
        help_text="The product these details belong to",
    )

    # Classification
    whiskey_type = models.CharField(
        max_length=30,
        choices=WhiskeyTypeChoices.choices,
        help_text="Type of whiskey",
    )
    whiskey_country = models.CharField(
        max_length=100,
        help_text="Country of origin",
    )
    whiskey_region = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Region within country (e.g., Speyside, Kentucky)",
    )

    # Production
    distillery = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Distillery name",
    )
    mash_bill = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Grain composition",
    )

    # Cask Information
    cask_type = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Primary cask type used",
    )
    cask_finish = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Finishing cask if any",
    )
    cask_strength = models.BooleanField(
        default=False,
        help_text="Whether this is a cask strength release",
    )
    single_cask = models.BooleanField(
        default=False,
        help_text="Whether this is from a single cask",
    )
    cask_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Cask number for single cask releases",
    )

    # Vintage/Batch Info
    vintage_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year of distillation",
    )
    bottling_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year of bottling",
    )
    batch_number = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Batch number",
    )

    # Peat
    peated = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether this whiskey is peated",
    )
    peat_level = models.CharField(
        max_length=20,
        choices=PeatLevelChoices.choices,
        blank=True,
        null=True,
        help_text="Level of peat",
    )

    # Production Methods
    chill_filtered = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether chill filtration was used",
    )
    color_added = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether color (E150a) was added",
    )

    class Meta:
        db_table = "whiskey_details"
        verbose_name = "Whiskey Details"
        verbose_name_plural = "Whiskey Details"

    def __str__(self):
        return f"Whiskey Details for {self.product}"


class PortWineDetails(models.Model):
    """
    Task Group 3: Extended details for port wine products.

    OneToOne relationship with DiscoveredProduct for port-specific fields.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # OneToOne relationship
    product = models.OneToOneField(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='port_details',
        help_text="The product these details belong to",
    )

    # Style
    style = models.CharField(
        max_length=20,
        choices=PortStyleChoices.choices,
        help_text="Port wine style",
    )
    indication_age = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Age indication (e.g., '20 Year', '10 Year')",
    )

    # Vintage Information
    harvest_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year of harvest/vintage",
    )
    bottling_year = models.IntegerField(
        blank=True,
        null=True,
        help_text="Year of bottling",
    )

    # Production
    grape_varieties = models.JSONField(
        default=list,
        blank=True,
        help_text="Grape varieties used",
    )
    quinta = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Quinta (estate) name",
    )
    douro_subregion = models.CharField(
        max_length=20,
        choices=DouroSubregionChoices.choices,
        blank=True,
        null=True,
        help_text="Douro subregion",
    )
    producer_house = models.CharField(
        max_length=200,
        help_text="Port house/producer name",
    )

    # Aging
    aging_vessel = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Type of vessel used for aging",
    )

    # Serving
    decanting_required = models.BooleanField(
        default=False,
        help_text="Whether decanting is recommended",
    )
    drinking_window = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Optimal drinking window (e.g., '2025-2060')",
    )

    class Meta:
        db_table = "port_wine_details"
        verbose_name = "Port Wine Details"
        verbose_name_plural = "Port Wine Details"

    def __str__(self):
        return f"Port Details for {self.product}"


# ============================================================
# Task Group 4: Related Data Tables (Awards, Prices, Ratings, Images)
# ============================================================


class ProductAward(models.Model):
    """
    Task Group 4: Awards won by products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='awards_rel',
        help_text="The product that won this award",
    )

    # Award Details
    competition = models.CharField(
        max_length=200,
        help_text="Competition/award name",
    )
    competition_country = models.CharField(
        max_length=100,
        help_text="Country where competition is held",
    )
    year = models.IntegerField(
        help_text="Year the award was given",
    )
    medal = models.CharField(
        max_length=20,
        choices=MedalChoices.choices,
        help_text="Medal/award level",
    )
    award_category = models.CharField(
        max_length=200,
        help_text="Category within the competition",
    )

    # Optional Details
    score = models.IntegerField(
        blank=True,
        null=True,
        help_text="Score given (if applicable)",
    )
    award_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to award page",
    )
    image_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to medal/certificate image",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_award"
        ordering = ["-year", "competition"]
        indexes = [
            models.Index(fields=["product", "year"]),
            models.Index(fields=["competition"]),
        ]
        verbose_name = "Product Award"
        verbose_name_plural = "Product Awards"

    def __str__(self):
        return f"{self.product} - {self.competition} {self.year} ({self.medal})"


class BrandAward(models.Model):
    """
    Task Group 4: Awards won by brands.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    brand = models.ForeignKey(
        DiscoveredBrand,
        on_delete=models.CASCADE,
        related_name='awards',
        help_text="The brand that won this award",
    )

    # Award Details
    competition = models.CharField(
        max_length=200,
        help_text="Competition/award name",
    )
    competition_country = models.CharField(
        max_length=100,
        help_text="Country where competition is held",
    )
    year = models.IntegerField(
        help_text="Year the award was given",
    )
    medal = models.CharField(
        max_length=20,
        choices=MedalChoices.choices,
        help_text="Medal/award level",
    )
    award_category = models.CharField(
        max_length=200,
        help_text="Category within the competition",
    )

    # Optional Details
    score = models.IntegerField(
        blank=True,
        null=True,
        help_text="Score given (if applicable)",
    )
    award_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to award page",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "brand_award"
        ordering = ["-year", "competition"]
        indexes = [
            models.Index(fields=["brand", "year"]),
            models.Index(fields=["competition"]),
        ]
        verbose_name = "Brand Award"
        verbose_name_plural = "Brand Awards"

    def __str__(self):
        return f"{self.brand} - {self.competition} {self.year} ({self.medal})"


class ProductPrice(models.Model):
    """
    Task Group 4: Price observations for products across retailers.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='prices',
        help_text="The product this price is for",
    )

    # Retailer Details
    retailer = models.CharField(
        max_length=200,
        help_text="Retailer name",
    )
    retailer_country = models.CharField(
        max_length=100,
        help_text="Retailer's country",
    )
    url = models.URLField(
        help_text="URL to product page at retailer",
    )

    # Pricing
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price in original currency",
    )
    currency = models.CharField(
        max_length=3,
        help_text="ISO 4217 currency code",
    )
    price_usd = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price normalized to USD",
    )
    price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price normalized to EUR",
    )

    # Stock
    in_stock = models.BooleanField(
        blank=True,
        null=True,
        help_text="Whether product is in stock",
    )

    # Timing
    date_observed = models.DateField(
        help_text="Date the price was observed",
    )

    class Meta:
        db_table = "product_price"
        ordering = ["-date_observed"]
        indexes = [
            models.Index(fields=["product", "retailer"]),
            models.Index(fields=["date_observed"]),
        ]
        verbose_name = "Product Price"
        verbose_name_plural = "Product Prices"

    def __str__(self):
        return f"{self.product} - {self.retailer}: {self.currency} {self.price}"


class ProductRating(models.Model):
    """
    Task Group 4: Ratings from various sources for products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='ratings_rel',
        help_text="The product this rating is for",
    )

    # Source
    source = models.CharField(
        max_length=200,
        help_text="Rating source/platform name",
    )
    source_country = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Country of the rating source",
    )

    # Rating
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        help_text="Rating score",
    )
    max_score = models.IntegerField(
        help_text="Maximum possible score (e.g., 100, 5)",
    )

    # Optional Details
    reviewer = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Reviewer name",
    )
    review_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL to full review",
    )
    date = models.DateField(
        blank=True,
        null=True,
        help_text="Date of the rating",
    )
    review_count = models.IntegerField(
        blank=True,
        null=True,
        help_text="Number of reviews (for aggregate scores)",
    )

    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product_rating"
        ordering = ["-score"]
        indexes = [
            models.Index(fields=["product", "source"]),
        ]
        verbose_name = "Product Rating"
        verbose_name_plural = "Product Ratings"

    def __str__(self):
        return f"{self.product} - {self.source}: {self.score}/{self.max_score}"


class ProductImage(models.Model):
    """
    Task Group 4: Images for products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='images_rel',
        help_text="The product this image belongs to",
    )

    # Image Details
    url = models.URLField(
        help_text="URL to the image",
    )
    image_type = models.CharField(
        max_length=20,
        choices=ImageTypeChoices.choices,
        help_text="Type of image",
    )
    source = models.CharField(
        max_length=200,
        help_text="Source of the image",
    )

    # Dimensions
    width = models.IntegerField(
        blank=True,
        null=True,
        help_text="Image width in pixels",
    )
    height = models.IntegerField(
        blank=True,
        null=True,
        help_text="Image height in pixels",
    )

    # Status
    is_primary = models.BooleanField(
        default=False,
        help_text="Whether this is the primary image",
    )

    class Meta:
        db_table = "product_image"
        ordering = ["-is_primary"]
        indexes = [
            models.Index(fields=["product"]),
        ]
        verbose_name = "Product Image"
        verbose_name_plural = "Product Images"

    def __str__(self):
        return f"{self.product} - {self.image_type}"


# ============================================================
# Task Group 7: Junction Tables (ProductSource, BrandSource)
# ============================================================


class ProductSource(models.Model):
    """
    Task Group 7: Junction table linking products to crawled sources.

    Tracks which CrawledSource contributed to which DiscoveredProduct
    with extraction metadata.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='product_sources',
        help_text="The product",
    )
    source = models.ForeignKey(
        'CrawledSource',
        on_delete=models.CASCADE,
        related_name='products',
        help_text="The source that mentioned this product",
    )

    # Extraction Metadata
    extraction_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence score for extraction (0.0-1.0)",
    )
    fields_extracted = models.JSONField(
        default=list,
        help_text="List of field names extracted from this source",
    )

    # Mention Details
    mention_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Type of mention",
    )
    mention_count = models.IntegerField(
        default=1,
        help_text="Number of times mentioned in this source",
    )

    # Timestamps
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_source"
        unique_together = ["product", "source"]
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Product Source"
        verbose_name_plural = "Product Sources"

    def __str__(self):
        return f"{self.product} <- {self.source}"


class BrandSource(models.Model):
    """
    Task Group 7: Junction table linking brands to crawled sources.

    Tracks which CrawledSource mentioned which DiscoveredBrand.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    brand = models.ForeignKey(
        DiscoveredBrand,
        on_delete=models.CASCADE,
        related_name='sources',
        help_text="The brand",
    )
    source = models.ForeignKey(
        'CrawledSource',
        on_delete=models.CASCADE,
        related_name='brands',
        help_text="The source that mentioned this brand",
    )

    # Extraction Metadata
    extraction_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence score for extraction (0.0-1.0)",
    )

    # Mention Details
    mention_type = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Type of mention",
    )
    mention_count = models.IntegerField(
        default=1,
        help_text="Number of times mentioned in this source",
    )

    # Timestamps
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "brand_source"
        unique_together = ["brand", "source"]
        indexes = [
            models.Index(fields=["brand"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Brand Source"
        verbose_name_plural = "Brand Sources"

    def __str__(self):
        return f"{self.brand} <- {self.source}"


# ============================================================
# Task Group 8: Per-Field Provenance Tracking
# ============================================================


class ProductFieldSource(models.Model):
    """
    Task Group 8: Per-field provenance tracking for products.

    Tracks which source contributed each field value to a product,
    enabling detailed provenance tracking and conflict detection.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
    product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='field_sources',
        help_text="The product",
    )
    source = models.ForeignKey(
        'CrawledSource',
        on_delete=models.CASCADE,
        related_name='field_extractions',
        help_text="The source that provided this field value",
    )

    # Field Information
    field_name = models.CharField(
        max_length=100,
        help_text="Name of the field",
    )
    extracted_value = models.TextField(
        help_text="The extracted value (stored as string)",
    )

    # Confidence
    confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Confidence score for this extraction (0.0-1.0)",
    )

    # Timestamps
    extracted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_field_source"
        unique_together = ["product", "field_name", "source"]
        indexes = [
            models.Index(fields=["product", "field_name"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Product Field Source"
        verbose_name_plural = "Product Field Sources"

    def __str__(self):
        return f"{self.product}.{self.field_name} <- {self.source}"


# ============================================================
# Task Group 12: ProductCandidate Staging Model
# ============================================================


class ProductCandidate(models.Model):
    """
    Task Group 12: Staging model for product candidates during deduplication.

    Stores extracted product mentions before they are matched to existing
    products or created as new products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Names
    raw_name = models.CharField(
        max_length=500,
        help_text="Original extracted product name",
    )
    normalized_name = models.CharField(
        max_length=500,
        help_text="Normalized product name for matching",
    )

    # Source
    source = models.ForeignKey(
        'CrawledSource',
        on_delete=models.CASCADE,
        related_name='product_candidates',
        help_text="Source this candidate was extracted from",
    )

    # Extracted Data
    extracted_data = models.JSONField(
        default=dict,
        help_text="All extracted data for this product",
    )

    # Match Status
    match_status = models.CharField(
        max_length=20,
        choices=MatchStatusChoices.choices,
        default=MatchStatusChoices.PENDING,
        help_text="Current matching status",
    )

    # Match Results
    matched_product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='matched_candidates',
        help_text="Matched existing product (if any)",
    )
    match_confidence = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
        help_text="Confidence of the match (0.0-1.0)",
    )
    match_method = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Method used for matching (gtin, fingerprint, fuzzy, ai)",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "product_candidate"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["match_status"]),
            models.Index(fields=["normalized_name"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Product Candidate"
        verbose_name_plural = "Product Candidates"

    def __str__(self):
        return f"{self.raw_name} ({self.match_status})"


# ============================================================
# Task Group 15: CrawlSchedule Model
# ============================================================


class CrawlSchedule(models.Model):
    """
    Task Group 15: Crawl scheduling with adaptive backoff.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Source
    source = models.ForeignKey(
        'DiscoverySourceConfig',
        on_delete=models.CASCADE,
        related_name='schedules',
        help_text="Discovery source this schedule is for",
    )

    # Timing
    next_run = models.DateTimeField(
        help_text="When the next crawl should run",
    )
    last_run = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the last crawl ran",
    )
    last_status = models.CharField(
        max_length=20,
        blank=True,
        help_text="Status of the last crawl",
    )

    # Backoff
    consecutive_errors = models.IntegerField(
        default=0,
        help_text="Number of consecutive errors",
    )
    current_backoff_hours = models.IntegerField(
        default=0,
        help_text="Current backoff in hours",
    )

    # Priority
    priority_boost = models.IntegerField(
        default=0,
        help_text="Priority boost for this schedule",
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this schedule is active",
    )

    class Meta:
        db_table = "crawl_schedule"
        ordering = ["next_run"]
        indexes = [
            models.Index(fields=["next_run", "is_active"]),
            models.Index(fields=["source"]),
        ]
        verbose_name = "Crawl Schedule"
        verbose_name_plural = "Crawl Schedules"

    def __str__(self):
        return f"Schedule for {self.source} - Next: {self.next_run}"


# ============================================================
# Task Group 16: PriceHistory Model
# ============================================================


class PriceHistory(models.Model):
    """
    Task Group 16: Historical price tracking for products.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='price_history_records',
        help_text="The product",
    )

    # Retailer
    retailer = models.CharField(
        max_length=200,
        help_text="Retailer name",
    )
    retailer_country = models.CharField(
        max_length=100,
        help_text="Retailer's country",
    )

    # Price
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Price in original currency",
    )
    currency = models.CharField(
        max_length=3,
        help_text="ISO 4217 currency code",
    )
    price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Price normalized to EUR",
    )

    # Timing
    observed_at = models.DateTimeField(
        help_text="When this price was observed",
    )
    source_url = models.URLField(
        blank=True,
        null=True,
        help_text="URL where price was observed",
    )

    class Meta:
        db_table = "price_history"
        ordering = ["-observed_at"]
        indexes = [
            models.Index(fields=["product", "retailer"]),
            models.Index(fields=["observed_at"]),
        ]
        verbose_name = "Price History"
        verbose_name_plural = "Price History Records"

    def __str__(self):
        return f"{self.product} - {self.retailer}: {self.currency} {self.price} ({self.observed_at})"


# ============================================================
# Task Group 17: PriceAlert Model
# ============================================================


class PriceAlert(models.Model):
    """
    Task Group 17: Price alerts for significant price changes.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationship
    product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.CASCADE,
        related_name='price_alerts',
        help_text="The product",
    )

    # Alert Details
    alert_type = models.CharField(
        max_length=20,
        choices=PriceAlertTypeChoices.choices,
        help_text="Type of alert",
    )
    threshold_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Threshold that triggered the alert",
    )
    triggered_value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Actual value that triggered the alert",
    )
    retailer = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Retailer where price change was detected",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    # Acknowledgment
    acknowledged = models.BooleanField(
        default=False,
        help_text="Whether this alert has been acknowledged",
    )
    acknowledged_by = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Who acknowledged this alert",
    )
    acknowledged_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When this alert was acknowledged",
    )

    class Meta:
        db_table = "price_alert"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["alert_type"]),
            models.Index(fields=["acknowledged"]),
        ]
        verbose_name = "Price Alert"
        verbose_name_plural = "Price Alerts"

    def __str__(self):
        return f"{self.product} - {self.alert_type}"


# ============================================================
# Task Group 18: NewRelease Model
# ============================================================


class NewRelease(models.Model):
    """
    Task Group 18: Tracking new and upcoming product releases.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Product Link (optional - may not exist yet)
    product = models.ForeignKey(
        'DiscoveredProduct',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='new_releases',
        help_text="Linked product if it exists",
    )

    # Release Information
    name = models.CharField(
        max_length=500,
        help_text="Product name",
    )
    brand = models.ForeignKey(
        DiscoveredBrand,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='new_releases',
        help_text="Brand if known",
    )
    product_type = models.CharField(
        max_length=20,
        choices=ProductType.choices,
        help_text="Type of product",
    )

    # Status
    release_status = models.CharField(
        max_length=20,
        choices=ReleaseStatusChoices.choices,
        help_text="Current release status",
    )

    # Dates
    announced_date = models.DateField(
        blank=True,
        null=True,
        help_text="When the release was announced",
    )
    expected_release_date = models.DateField(
        blank=True,
        null=True,
        help_text="Expected release date",
    )
    actual_release_date = models.DateField(
        blank=True,
        null=True,
        help_text="Actual release date",
    )

    # Pricing
    expected_price_eur = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        blank=True,
        null=True,
        help_text="Expected price in EUR",
    )

    # Limited Edition Info
    limited_edition = models.BooleanField(
        default=False,
        help_text="Whether this is a limited edition",
    )
    expected_bottle_count = models.IntegerField(
        blank=True,
        null=True,
        help_text="Expected number of bottles",
    )

    # Interest Metrics
    hype_score = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        blank=True,
        null=True,
        help_text="Calculated hype/interest score (1-100)",
    )

    # Sources
    source_urls = models.JSONField(
        default=list,
        help_text="URLs where this release was mentioned",
    )

    # Notes
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes about the release",
    )

    # Tracking
    is_tracked = models.BooleanField(
        default=True,
        help_text="Whether to continue tracking this release",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "new_release"
        ordering = ["-expected_release_date"]
        indexes = [
            models.Index(fields=["release_status"]),
            models.Index(fields=["product_type"]),
            models.Index(fields=["expected_release_date"]),
            models.Index(fields=["is_tracked"]),
        ]
        verbose_name = "New Release"
        verbose_name_plural = "New Releases"

    def __str__(self):
        return f"{self.name} ({self.release_status})"
