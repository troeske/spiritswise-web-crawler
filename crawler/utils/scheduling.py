"""
Scheduling utilities for CrawlSchedule next_run calculation.

Task Group 15: CrawlSchedule Model
Provides utilities for calculating next run times with exponential backoff.
"""

from datetime import timedelta
from django.utils import timezone


# Base intervals for schedule types
SCHEDULE_INTERVALS = {
    "daily": timedelta(hours=24),
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
    "on_demand": None,  # On-demand doesn't auto-schedule
}

# Maximum backoff delay (7 days) to prevent excessive delays
MAX_BACKOFF_DELAY = timedelta(days=7)


def calculate_next_run(schedule_type: str, from_time=None):
    """
    Calculate the next run time based on schedule type.

    Args:
        schedule_type: One of 'daily', 'weekly', 'monthly', 'on_demand'
        from_time: Base time to calculate from (defaults to now)

    Returns:
        datetime or None: Next scheduled run time, or None for on_demand
    """
    if from_time is None:
        from_time = timezone.now()

    interval = SCHEDULE_INTERVALS.get(schedule_type)

    if interval is None:
        # on_demand schedules don't automatically schedule
        return None

    return from_time + interval


def calculate_next_run_with_backoff(
    schedule_type: str,
    from_time=None,
    error_count: int = 0,
    paused_until=None,
):
    """
    Calculate next run time with exponential backoff for errors.

    Applies exponential backoff when error_count > 0:
    - 0 errors: normal interval
    - 1 error: 2x interval
    - 2 errors: 4x interval
    - n errors: 2^n x interval (capped at MAX_BACKOFF_DELAY)

    Args:
        schedule_type: One of 'daily', 'weekly', 'monthly', 'on_demand'
        from_time: Base time to calculate from (defaults to now)
        error_count: Number of consecutive errors (default 0)
        paused_until: If set, next_run should be at least this time

    Returns:
        datetime or None: Next scheduled run time with backoff applied,
                         or None for on_demand
    """
    if from_time is None:
        from_time = timezone.now()

    interval = SCHEDULE_INTERVALS.get(schedule_type)

    if interval is None:
        # on_demand schedules don't automatically schedule
        return None

    # Apply exponential backoff: interval * 2^error_count
    if error_count > 0:
        backoff_multiplier = 2 ** error_count
        backoff_interval = interval * backoff_multiplier

        # Cap at maximum backoff delay
        if backoff_interval > MAX_BACKOFF_DELAY:
            backoff_interval = MAX_BACKOFF_DELAY

        next_run = from_time + backoff_interval
    else:
        next_run = from_time + interval

    # Respect paused_until if set and is after calculated next_run
    if paused_until is not None and paused_until > next_run:
        next_run = paused_until

    return next_run


def reset_error_backoff(schedule):
    """
    Reset error count and paused_until after successful crawl.

    Args:
        schedule: CrawlSchedule instance to reset
    """
    schedule.error_count = 0
    schedule.paused_until = None
    schedule.save(update_fields=["error_count", "paused_until"])


def apply_error_backoff(schedule, error_count_increment: int = 1):
    """
    Apply error backoff to a schedule after a failed crawl.

    Args:
        schedule: CrawlSchedule instance to update
        error_count_increment: How much to increment error_count (default 1)
    """
    schedule.error_count += error_count_increment
    schedule.next_run = calculate_next_run_with_backoff(
        schedule.schedule_type,
        timezone.now(),
        schedule.error_count,
        schedule.paused_until,
    )
    schedule.save(update_fields=["error_count", "next_run"])


def get_due_schedules():
    """
    Get all active schedules that are due to run.

    Returns:
        QuerySet: CrawlSchedule instances ready to be executed
    """
    from crawler.models import CrawlSchedule

    now = timezone.now()

    return CrawlSchedule.objects.filter(
        is_active=True,
        next_run__lte=now,
    ).select_related("source").order_by(
        "-priority_boost",  # Higher priority first
        "next_run",  # Then by when they were due
    )
