"""
Celery configuration for Web Crawler Microservice.

This module configures Celery for asynchronous task processing
with separate task queues for crawl and search operations.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("web_crawler")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Configure task queues for different operations
app.conf.task_queues = {
    "crawl": {
        "exchange": "crawl",
        "routing_key": "crawl",
    },
    "search": {
        "exchange": "search",
        "routing_key": "search",
    },
    "enrichment": {
        "exchange": "enrichment",
        "routing_key": "enrichment",
    },
    "discovery": {
        "exchange": "discovery",
        "routing_key": "discovery",
    },
    "default": {
        "exchange": "default",
        "routing_key": "default",
    },
}

# Default task routing
app.conf.task_default_queue = "default"
app.conf.task_default_exchange = "default"
app.conf.task_default_routing_key = "default"

# Route specific tasks to their queues
app.conf.task_routes = {
    "crawler.tasks.crawl_*": {"queue": "crawl"},
    "crawler.tasks.search_*": {"queue": "search"},
    "crawler.tasks.process_source": {"queue": "crawl"},
    "crawler.tasks.keyword_search": {"queue": "search"},
    "crawler.tasks.enrich_skeletons": {"queue": "enrichment"},
    "crawler.tasks.process_enrichment_queue": {"queue": "enrichment"},
    # Unified scheduling tasks
    "crawler.tasks.check_due_schedules": {"queue": "default"},
    "crawler.tasks.run_scheduled_job": {"queue": "discovery"},
    "crawler.tasks.trigger_scheduled_job_manual": {"queue": "discovery"},
}

# Configure Celery Beat schedule for periodic tasks
app.conf.beat_schedule = {
    "check-due-sources-every-5-minutes": {
        "task": "crawler.tasks.check_due_sources",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
    "check-due-keywords-every-15-minutes": {
        "task": "crawler.tasks.check_due_keywords",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
    },
    # Competition enrichment tasks
    "enrich-skeletons-every-30-minutes": {
        "task": "crawler.tasks.enrich_skeletons",
        "schedule": crontab(minute="*/30"),  # Every 30 minutes
        "kwargs": {"limit": 50},
    },
    "process-enrichment-queue-every-10-minutes": {
        "task": "crawler.tasks.process_enrichment_queue",
        "schedule": crontab(minute="*/10"),  # Every 10 minutes
        "kwargs": {"max_urls": 100},
    },
    # Unified scheduling task
    "check-due-schedules-every-5-minutes": {
        "task": "crawler.tasks.check_due_schedules",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery configuration."""
    print(f"Request: {self.request!r}")
