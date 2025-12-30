"""
Price Trend Calculation Service.

Task Group 17: Price Trend Calculation & Alerts

Provides:
- 30-day and 90-day trend calculation
- Price stability score calculation
- Min/max price tracking
- Alert threshold checking
"""

from datetime import timedelta
from decimal import Decimal
from statistics import stdev
from typing import Optional

from django.db.models import Avg, Min, Max
from django.utils import timezone


def calculate_price_trends(product) -> None:
    """
    Calculate price trends for a product based on price history.

    Calculates:
    - 30-day trend (rising, stable, falling) and percentage change
    - 90-day trend (rising, stable, falling) and percentage change
    - Price stability score (1-10, inverse of volatility)
    - Lowest/highest price ever with dates

    Args:
        product: DiscoveredProduct instance

    Updates the product in-place and saves to database.
    """
    from crawler.models import PriceHistory, PriceTrendChoices

    now = timezone.now()

    # Get price history for last 90 days
    history_90d = PriceHistory.objects.filter(
        product=product,
        observed_at__gte=now - timedelta(days=90),
    ).order_by("observed_at")

    # Get price history for last 30 days
    history_30d = history_90d.filter(observed_at__gte=now - timedelta(days=30))

    # Calculate 30-day trend
    trend_30d, change_30d_pct = _calculate_trend(history_30d)
    if trend_30d:
        product.price_trend_30d = trend_30d
        product.price_change_30d_pct = change_30d_pct

    # Calculate 90-day trend
    trend_90d, change_90d_pct = _calculate_trend(history_90d)
    if trend_90d:
        product.price_trend_90d = trend_90d
        product.price_change_90d_pct = change_90d_pct

    # Calculate price stability score
    stability_score = _calculate_stability_score(history_90d)
    if stability_score is not None:
        product.price_stability_score = stability_score

    # Update min/max prices
    _update_min_max_prices(product, history_90d)

    # Save all updates
    update_fields = [
        "price_trend_30d",
        "price_change_30d_pct",
        "price_trend_90d",
        "price_change_90d_pct",
        "price_stability_score",
        "lowest_price_ever_eur",
        "lowest_price_date",
        "highest_price_ever_eur",
        "highest_price_date",
    ]
    product.save(update_fields=update_fields)


def _calculate_trend(history_queryset) -> tuple[Optional[str], Optional[Decimal]]:
    """
    Calculate price trend from a queryset of price history.

    Trend calculation:
    - Split history into two halves (first half vs second half)
    - Calculate average price of each half
    - Compare: >5% increase = rising, <-5% decrease = falling, else stable

    Args:
        history_queryset: QuerySet of PriceHistory records

    Returns:
        Tuple of (trend_choice, percentage_change) or (None, None) if insufficient data
    """
    from crawler.models import PriceTrendChoices

    count = history_queryset.count()
    if count < 2:
        return None, None

    # Convert to list for splitting
    history_list = list(history_queryset)
    mid_point = len(history_list) // 2

    # First half (older prices)
    first_half = history_list[:mid_point]
    first_half_prices = [h.price_eur for h in first_half if h.price_eur]

    # Second half (newer prices)
    second_half = history_list[mid_point:]
    second_half_prices = [h.price_eur for h in second_half if h.price_eur]

    if not first_half_prices or not second_half_prices:
        return None, None

    first_avg = sum(first_half_prices) / len(first_half_prices)
    second_avg = sum(second_half_prices) / len(second_half_prices)

    if first_avg == 0:
        return None, None

    # Calculate percentage change
    change_pct = ((second_avg - first_avg) / first_avg) * 100
    change_pct_decimal = Decimal(str(round(change_pct, 2)))

    # Classify trend
    if change_pct > 5:
        trend = PriceTrendChoices.RISING
    elif change_pct < -5:
        trend = PriceTrendChoices.FALLING
    else:
        trend = PriceTrendChoices.STABLE

    return trend, change_pct_decimal


def _calculate_stability_score(history_queryset) -> Optional[int]:
    """
    Calculate price stability score from price history.

    Stability is the inverse of volatility (standard deviation).
    Score range: 1 (very volatile) to 10 (very stable)

    Args:
        history_queryset: QuerySet of PriceHistory records

    Returns:
        Stability score (1-10) or None if insufficient data
    """
    prices = [
        float(h.price_eur) for h in history_queryset
        if h.price_eur is not None
    ]

    if len(prices) < 2:
        return None

    # Calculate coefficient of variation (std dev / mean)
    mean_price = sum(prices) / len(prices)
    if mean_price == 0:
        return None

    try:
        std_dev = stdev(prices)
        coefficient_of_variation = std_dev / mean_price
    except (ValueError, ZeroDivisionError):
        return None

    # Convert CV to stability score
    # CV close to 0 = very stable (score 10)
    # CV close to 1 or higher = very volatile (score 1)
    # Using a logarithmic scale for better distribution

    if coefficient_of_variation <= 0.01:
        # Very stable (< 1% variation)
        score = 10
    elif coefficient_of_variation <= 0.05:
        # Stable (1-5% variation)
        score = 9
    elif coefficient_of_variation <= 0.10:
        # Mostly stable (5-10% variation)
        score = 8
    elif coefficient_of_variation <= 0.15:
        # Moderately stable (10-15% variation)
        score = 7
    elif coefficient_of_variation <= 0.20:
        # Some volatility (15-20% variation)
        score = 6
    elif coefficient_of_variation <= 0.25:
        # Moderate volatility (20-25% variation)
        score = 5
    elif coefficient_of_variation <= 0.30:
        # Volatile (25-30% variation)
        score = 4
    elif coefficient_of_variation <= 0.40:
        # Very volatile (30-40% variation)
        score = 3
    elif coefficient_of_variation <= 0.50:
        # Highly volatile (40-50% variation)
        score = 2
    else:
        # Extremely volatile (> 50% variation)
        score = 1

    return score


def _update_min_max_prices(product, history_queryset) -> None:
    """
    Update the lowest and highest price ever observed.

    Args:
        product: DiscoveredProduct instance
        history_queryset: QuerySet of PriceHistory records
    """
    # Get all-time price history (not just last 90 days)
    from crawler.models import PriceHistory

    all_history = PriceHistory.objects.filter(product=product)

    if not all_history.exists():
        return

    # Find minimum price
    min_record = all_history.order_by("price_eur").first()
    if min_record and min_record.price_eur:
        # Only update if it's lower than current lowest or no current lowest
        if (product.lowest_price_ever_eur is None or
                min_record.price_eur < product.lowest_price_ever_eur):
            product.lowest_price_ever_eur = min_record.price_eur
            product.lowest_price_date = min_record.observed_at.date()

    # Find maximum price
    max_record = all_history.order_by("-price_eur").first()
    if max_record and max_record.price_eur:
        # Only update if it's higher than current highest or no current highest
        if (product.highest_price_ever_eur is None or
                max_record.price_eur > product.highest_price_ever_eur):
            product.highest_price_ever_eur = max_record.price_eur
            product.highest_price_date = max_record.observed_at.date()


def check_price_alerts(product, price_history) -> None:
    """
    Check if a new price should trigger alerts.

    Creates PriceAlert records for:
    - price_drop: Price dropped below user-set threshold
    - new_low: Price is new all-time low

    Args:
        product: DiscoveredProduct instance
        price_history: PriceHistory instance with the new price
    """
    from crawler.models import PriceAlert, PriceAlertTypeChoices

    new_price_eur = price_history.price_eur
    if new_price_eur is None:
        return

    alerts_created = []

    # Check threshold alert (price_drop)
    if (product.price_alert_threshold_eur is not None and
            new_price_eur < product.price_alert_threshold_eur and
            not product.price_alert_triggered):
        # Price dropped below threshold
        alert = PriceAlert.objects.create(
            product=product,
            alert_type=PriceAlertTypeChoices.PRICE_DROP,
            threshold_value=product.price_alert_threshold_eur,
            triggered_value=new_price_eur,
            retailer=price_history.retailer,
        )
        alerts_created.append(alert)

        # Mark as triggered on product
        product.price_alert_triggered = True
        product.save(update_fields=["price_alert_triggered"])

    # Check for new all-time low
    if (product.lowest_price_ever_eur is not None and
            new_price_eur < product.lowest_price_ever_eur):
        # New all-time low
        alert = PriceAlert.objects.create(
            product=product,
            alert_type=PriceAlertTypeChoices.NEW_LOW,
            triggered_value=new_price_eur,
            retailer=price_history.retailer,
        )
        alerts_created.append(alert)

    return alerts_created


def calculate_all_product_trends() -> dict:
    """
    Calculate price trends for all products with price history.

    This is designed to be run as a nightly batch job.

    Returns:
        Dict with counts of products processed and errors
    """
    from crawler.models import DiscoveredProduct, PriceHistory

    # Get products with price history
    products_with_history = DiscoveredProduct.objects.filter(
        price_history_rel__isnull=False
    ).distinct()

    processed = 0
    errors = 0

    for product in products_with_history:
        try:
            calculate_price_trends(product)
            processed += 1
        except Exception as e:
            errors += 1
            # Log error but continue processing other products
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error calculating trends for product {product.id}: {e}")

    return {
        "processed": processed,
        "errors": errors,
        "total": products_with_history.count(),
    }
