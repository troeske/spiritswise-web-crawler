"""
Django admin configuration for Web Crawler models.

Task Group 8: Admin Dashboard & Source Management
Task Group 21: ProductAvailability Admin
Task Group 22: CategoryInsight Admin
Task Group 23: PurchaseRecommendation Admin
Task Group 24: ShopInventory Admin
Task Group 26: CrawlerMetrics Admin

Provides user-friendly interfaces for managing crawler sources,
keywords, jobs, costs, errors, and discovered products.

Reference: spiritswise-ai-enhancement-service/ai_enhancement_engine/crawler_admin.py
"""

import json
from datetime import timedelta

from django.contrib import admin
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate, TruncWeek, TruncMonth
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from crawler.models import (
    CrawlerSource,
    CrawlerKeyword,
    CrawlJob,
    CrawledURL,
    DiscoveredProduct,
    CrawledArticle,
    CrawlCost,
    CrawlError,
    ProductAvailability,
    CategoryInsight,
    PurchaseRecommendation,
    ShopInventory,
    CrawlerMetrics,
    # New models
    DiscoveredBrand,
    WhiskeyDetails,
    PortWineDetails,
    ProductAward,
    BrandAward,
    ProductPrice,
    ProductRating,
    ProductImage,
    ProductSource,
    BrandSource,
    ProductFieldSource,
    ProductCandidate,
    CrawlSchedule,
    PriceHistory,
    PriceAlert,
    NewRelease,
)

# Import task for trigger_crawl action
from crawler.tasks import trigger_manual_crawl


@admin.register(CrawlerSource)
class CrawlerSourceAdmin(admin.ModelAdmin):
    """
    Admin interface for crawler sources.

    Task 8.2: Implements source management with fieldsets, filters,
    search, and admin actions.
    """

    list_display = [
        "name",
        "category",
        "is_active_badge",
        "priority",
        "last_crawl_at",
        "total_products_found",
        "last_crawl_status_badge",
    ]
    list_filter = [
        "is_active",
        "category",
        "age_gate_type",
        "requires_tier3",
        "discovery_method",
    ]
    search_fields = ["name", "base_url"]
    readonly_fields = [
        "id",
        "last_crawl_at",
        "next_crawl_at",
        "last_crawl_status",
        "total_products_found",
        "created_at",
        "updated_at",
    ]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["-priority", "name"]

    fieldsets = (
        ("Identity", {
            "fields": ("id", "name", "slug", "base_url"),
        }),
        ("Classification", {
            "fields": ("category", "product_types"),
        }),
        ("Crawl Configuration", {
            "fields": (
                "is_active",
                "priority",
                "crawl_frequency_hours",
                "rate_limit_requests_per_minute",
            ),
        }),
        ("Age Gate", {
            "fields": (
                "age_gate_type",
                "age_gate_cookies",
            ),
            "classes": ("collapse",),
        }),
        ("Technical", {
            "fields": (
                "requires_javascript",
                "requires_proxy",
                "requires_tier3",
                "requires_authentication",
                "custom_headers",
                "discovery_method",
            ),
            "classes": ("collapse",),
        }),
        ("URL Patterns", {
            "fields": (
                "product_url_patterns",
                "pagination_pattern",
                "sitemap_url",
            ),
            "classes": ("collapse",),
        }),
        ("Compliance", {
            "fields": (
                "robots_txt_compliant",
                "tos_compliant",
                "compliance_notes",
            ),
        }),
        ("Status", {
            "fields": (
                "last_crawl_at",
                "next_crawl_at",
                "last_crawl_status",
                "total_products_found",
            ),
        }),
        ("Metadata", {
            "fields": ("notes", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    actions = ["trigger_crawl", "enable_sources", "disable_sources", "reset_schedule"]

    def is_active_badge(self, obj):
        """Display active status as colored badge."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 2px 8px; border-radius: 4px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; '
            'padding: 2px 8px; border-radius: 4px;">Inactive</span>'
        )
    is_active_badge.short_description = "Active"
    is_active_badge.admin_order_field = "is_active"

    def last_crawl_status_badge(self, obj):
        """Display crawl status as colored badge."""
        if not obj.is_active:
            color = "#6c757d"
            text = "Disabled"
        elif obj.last_crawl_status == "completed":
            color = "#28a745"
            text = "OK"
        elif obj.last_crawl_status == "failed":
            color = "#dc3545"
            text = "Failed"
        elif obj.last_crawl_status == "running":
            color = "#007bff"
            text = "Running"
        elif obj.last_crawl_status == "pending":
            color = "#ffc107"
            text = "Pending"
        else:
            color = "#6c757d"
            text = "Never"
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 4px;">{}</span>',
            color, text
        )
    last_crawl_status_badge.short_description = "Status"

    @admin.action(description="Trigger crawl now")
    def trigger_crawl(self, request, queryset):
        """Trigger immediate crawl for selected active sources."""
        count = 0
        for source in queryset.filter(is_active=True):
            # Create a CrawlJob and dispatch task
            job = CrawlJob.objects.create(source=source)
            trigger_manual_crawl.apply_async(args=[str(source.id)])
            count += 1
        self.message_user(
            request,
            f"Triggered crawl for {count} source(s). Jobs will be processed shortly."
        )

    @admin.action(description="Disable selected sources")
    def disable_sources(self, request, queryset):
        """Disable selected sources."""
        count = queryset.update(is_active=False)
        self.message_user(request, f"Disabled {count} source(s).")

    @admin.action(description="Enable selected sources")
    def enable_sources(self, request, queryset):
        """Enable selected sources."""
        count = queryset.update(is_active=True)
        self.message_user(request, f"Enabled {count} source(s).")

    @admin.action(description="Reset crawl schedule (crawl ASAP)")
    def reset_schedule(self, request, queryset):
        """Reset next_crawl_at to now for selected sources."""
        count = queryset.update(next_crawl_at=timezone.now())
        self.message_user(request, f"Reset schedule for {count} source(s).")


@admin.register(CrawlJob)
class CrawlJobAdmin(admin.ModelAdmin):
    """
    Admin interface for crawl jobs.

    Task 8.3: Read-only view of crawl job status and metrics.
    """

    list_display = [
        "id_short",
        "source",
        "status_badge",
        "started_at",
        "completed_at",
        "pages_crawled",
        "products_found",
        "errors_count",
        "duration_display",
    ]
    list_filter = [
        "status",
        "source",
        ("created_at", admin.DateFieldListFilter),
    ]
    search_fields = ["source__name", "id"]
    readonly_fields = [
        "id",
        "source",
        "status",
        "created_at",
        "started_at",
        "completed_at",
        "pages_crawled",
        "products_found",
        "products_new",
        "products_updated",
        "errors_count",
        "error_message",
        "error_details",
        "results_summary",
    ]
    ordering = ["-created_at"]

    fieldsets = (
        ("Job Information", {
            "fields": ("id", "source", "status"),
        }),
        ("Timing", {
            "fields": ("created_at", "started_at", "completed_at"),
        }),
        ("Metrics", {
            "fields": (
                "pages_crawled",
                "products_found",
                "products_new",
                "products_updated",
                "errors_count",
            ),
        }),
        ("Error Details", {
            "fields": ("error_message", "error_details"),
            "classes": ("collapse",),
        }),
        ("Results", {
            "fields": ("results_summary",),
            "classes": ("collapse",),
        }),
    )

    def id_short(self, obj):
        """Display shortened job ID."""
        return str(obj.id)[:8]
    id_short.short_description = "Job ID"

    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            "pending": "#ffc107",
            "running": "#007bff",
            "completed": "#28a745",
            "failed": "#dc3545",
            "cancelled": "#6c757d",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 4px;">{}</span>',
            color, obj.status.title()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def duration_display(self, obj):
        """Display job duration in human-readable format."""
        if obj.duration_seconds:
            seconds = obj.duration_seconds
            if seconds < 60:
                return f"{seconds:.1f}s"
            elif seconds < 3600:
                return f"{seconds / 60:.1f}m"
            else:
                return f"{seconds / 3600:.1f}h"
        return "-"
    duration_display.short_description = "Duration"

    def has_add_permission(self, request):
        """Disable manual job creation from admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing jobs (read-only)."""
        return False


@admin.register(CrawlCost)
class CrawlCostAdmin(admin.ModelAdmin):
    """
    Admin interface for cost tracking.

    Task 8.4: Displays cost records with custom aggregation view.
    """

    list_display = [
        "timestamp",
        "service_badge",
        "cost_display",
        "request_count",
        "crawl_job_link",
    ]
    list_filter = [
        "service",
        ("timestamp", admin.DateFieldListFilter),
    ]
    readonly_fields = [
        "id",
        "service",
        "cost_cents",
        "crawl_job",
        "request_count",
        "timestamp",
    ]
    ordering = ["-timestamp"]

    def service_badge(self, obj):
        """Display service as colored badge."""
        colors = {
            "serpapi": "#17a2b8",
            "scrapingbee": "#6f42c1",
            "openai": "#28a745",
        }
        color = colors.get(obj.service, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 4px;">{}</span>',
            color, obj.service.upper()
        )
    service_badge.short_description = "Service"
    service_badge.admin_order_field = "service"

    def cost_display(self, obj):
        """Display cost in dollars."""
        return f"${obj.cost_cents / 100:.2f}"
    cost_display.short_description = "Cost"
    cost_display.admin_order_field = "cost_cents"

    def crawl_job_link(self, obj):
        """Display link to crawl job."""
        if obj.crawl_job:
            return format_html(
                '<a href="/admin/crawler/crawljob/{}/change/">{}</a>',
                obj.crawl_job.id, str(obj.crawl_job.id)[:8]
            )
        return "-"
    crawl_job_link.short_description = "Job"

    def has_add_permission(self, request):
        """Disable manual cost creation."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing costs (read-only)."""
        return False

    def get_urls(self):
        """Add custom URL for cost summary view."""
        urls = super().get_urls()
        custom_urls = [
            path(
                "summary/",
                self.admin_site.admin_view(self.cost_summary_view),
                name="crawler_crawlcost_summary",
            ),
        ]
        return custom_urls + urls

    def cost_summary_view(self, request):
        """
        Custom view for cost aggregation.

        Displays costs by day/week/month with breakdown by service.
        """
        now = timezone.now()
        one_week_ago = now - timedelta(days=7)
        one_month_ago = now - timedelta(days=30)

        # Daily costs (last 7 days)
        daily_costs = (
            CrawlCost.objects.filter(timestamp__gte=one_week_ago)
            .annotate(date=TruncDate("timestamp"))
            .values("date", "service")
            .annotate(total_cents=Sum("cost_cents"), count=Count("id"))
            .order_by("-date", "service")
        )

        # Weekly costs (last 4 weeks)
        weekly_costs = (
            CrawlCost.objects.filter(timestamp__gte=one_month_ago)
            .annotate(week=TruncWeek("timestamp"))
            .values("week", "service")
            .annotate(total_cents=Sum("cost_cents"), count=Count("id"))
            .order_by("-week", "service")
        )

        # Monthly totals by service
        monthly_by_service = (
            CrawlCost.objects.filter(timestamp__gte=one_month_ago)
            .values("service")
            .annotate(total_cents=Sum("cost_cents"), count=Count("id"))
            .order_by("service")
        )

        # Grand totals
        total_costs = CrawlCost.objects.aggregate(
            total=Sum("cost_cents"),
            count=Count("id"),
        )

        context = {
            **self.admin_site.each_context(request),
            "title": "Cost Summary",
            "daily_costs": list(daily_costs),
            "weekly_costs": list(weekly_costs),
            "monthly_by_service": list(monthly_by_service),
            "total_costs": total_costs,
            "opts": self.model._meta,
        }

        return TemplateResponse(
            request,
            "admin/crawler/crawlcost/summary.html",
            context,
        )

    def changelist_view(self, request, extra_context=None):
        """Add summary link to changelist view."""
        extra_context = extra_context or {}
        extra_context["show_summary_link"] = True
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(CrawlError)
class CrawlErrorAdmin(admin.ModelAdmin):
    """
    Admin interface for crawl errors.

    Task 8.5: Filterable error logs with full detail view.
    """

    list_display = [
        "timestamp",
        "source",
        "url_truncated",
        "error_type_badge",
        "resolved_badge",
    ]
    list_filter = [
        "source",
        "error_type",
        "resolved",
        ("timestamp", admin.DateFieldListFilter),
    ]
    search_fields = ["url", "message"]
    readonly_fields = [
        "id",
        "source",
        "url",
        "error_type",
        "message",
        "stack_trace_formatted",
        "tier_used",
        "response_status",
        "response_headers_formatted",
        "timestamp",
    ]
    ordering = ["-timestamp"]

    fieldsets = (
        ("Error Information", {
            "fields": ("id", "source", "url", "error_type", "message"),
        }),
        ("Request Context", {
            "fields": ("tier_used", "response_status"),
        }),
        ("Response Headers", {
            "fields": ("response_headers_formatted",),
            "classes": ("collapse",),
        }),
        ("Stack Trace", {
            "fields": ("stack_trace_formatted",),
            "classes": ("collapse",),
        }),
        ("Status", {
            "fields": ("timestamp", "resolved"),
        }),
    )

    actions = ["mark_resolved", "mark_unresolved"]

    def url_truncated(self, obj):
        """Display truncated URL."""
        max_length = 50
        if len(obj.url) > max_length:
            return obj.url[:max_length] + "..."
        return obj.url
    url_truncated.short_description = "URL"

    def error_type_badge(self, obj):
        """Display error type as colored badge."""
        colors = {
            "connection": "#dc3545",
            "timeout": "#ffc107",
            "blocked": "#dc3545",
            "age_gate": "#6f42c1",
            "rate_limit": "#fd7e14",
            "parse": "#17a2b8",
            "api": "#007bff",
            "unknown": "#6c757d",
        }
        color = colors.get(obj.error_type, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 4px;">{}</span>',
            color, obj.error_type.replace("_", " ").title()
        )
    error_type_badge.short_description = "Type"
    error_type_badge.admin_order_field = "error_type"

    def resolved_badge(self, obj):
        """Display resolved status as colored badge."""
        if obj.resolved:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 2px 8px; border-radius: 4px;">Resolved</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; '
            'padding: 2px 8px; border-radius: 4px;">Open</span>'
        )
    resolved_badge.short_description = "Status"
    resolved_badge.admin_order_field = "resolved"

    def stack_trace_formatted(self, obj):
        """Display stack trace in a preformatted block."""
        if obj.stack_trace:
            return format_html(
                '<pre style="white-space: pre-wrap; word-wrap: break-word; '
                'background: #f5f5f5; padding: 10px; border-radius: 4px;">{}</pre>',
                obj.stack_trace
            )
        return "-"
    stack_trace_formatted.short_description = "Stack Trace"

    def response_headers_formatted(self, obj):
        """Display response headers as formatted JSON."""
        if obj.response_headers:
            formatted = json.dumps(obj.response_headers, indent=2)
            return format_html(
                '<pre style="white-space: pre-wrap; word-wrap: break-word; '
                'background: #f5f5f5; padding: 10px; border-radius: 4px;">{}</pre>',
                formatted
            )
        return "-"
    response_headers_formatted.short_description = "Response Headers"

    @admin.action(description="Mark selected errors as resolved")
    def mark_resolved(self, request, queryset):
        """Mark selected errors as resolved."""
        count = queryset.update(resolved=True)
        self.message_user(request, f"Marked {count} error(s) as resolved.")

    @admin.action(description="Mark selected errors as unresolved")
    def mark_unresolved(self, request, queryset):
        """Mark selected errors as unresolved."""
        count = queryset.update(resolved=False)
        self.message_user(request, f"Marked {count} error(s) as unresolved.")

    def has_add_permission(self, request):
        """Disable manual error creation."""
        return False


@admin.register(DiscoveredProduct)
class DiscoveredProductAdmin(admin.ModelAdmin):
    """
    Admin interface for discovered products.

    Task 8.6: Product review with status badges and actions.
    """

    list_display = [
        "product_name",
        "product_type",
        "status_badge",
        "discovery_source_badge",
        "source",
        "discovered_at",
    ]
    list_filter = [
        "status",
        "product_type",
        "discovery_source",
        "source",
    ]
    search_fields = ["extracted_data", "source_url"]
    readonly_fields = [
        "id",
        "source",
        "source_url",
        "crawl_job",
        "fingerprint",
        "raw_content",
        "raw_content_hash",
        "extracted_data_formatted",
        "enriched_data_formatted",
        "awards_formatted",
        "extraction_confidence",
        "matched_product_id",
        "match_confidence",
        "discovered_at",
        "reviewed_at",
        "reviewed_by",
    ]
    ordering = ["-discovered_at"]

    fieldsets = (
        ("Product Information", {
            "fields": ("id", "product_type", "fingerprint"),
        }),
        ("Source", {
            "fields": ("source", "source_url", "crawl_job", "discovery_source"),
        }),
        ("Extracted Data", {
            "fields": ("extracted_data_formatted", "extraction_confidence"),
        }),
        ("Enriched Data", {
            "fields": ("enriched_data_formatted",),
            "classes": ("collapse",),
        }),
        ("Awards", {
            "fields": ("awards_formatted",),
            "classes": ("collapse",),
        }),
        ("Review Status", {
            "fields": ("status", "reviewed_at", "reviewed_by"),
        }),
        ("Matching", {
            "fields": ("matched_product_id", "match_confidence"),
            "classes": ("collapse",),
        }),
        ("Raw Content", {
            "fields": ("raw_content", "raw_content_hash"),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("discovered_at",),
        }),
    )

    actions = ["approve_products", "reject_products", "mark_duplicate"]

    def product_name(self, obj):
        """Display product name from extracted data."""
        name = obj.extracted_data.get("name", "Unknown")
        if len(name) > 50:
            return name[:50] + "..."
        return name
    product_name.short_description = "Name"

    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            "pending": "#ffc107",
            "approved": "#28a745",
            "rejected": "#dc3545",
            "duplicate": "#6c757d",
            "merged": "#17a2b8",
            "skeleton": "#6f42c1",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 4px;">{}</span>',
            color, obj.status.title()
        )
    status_badge.short_description = "Status"
    status_badge.admin_order_field = "status"

    def discovery_source_badge(self, obj):
        """Display discovery source as colored badge."""
        colors = {
            "competition": "#6f42c1",
            "hub_spoke": "#17a2b8",
            "search": "#28a745",
            "direct": "#6c757d",
        }
        color = colors.get(obj.discovery_source, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 4px;">{}</span>',
            color, obj.discovery_source.replace("_", " ").title()
        )
    discovery_source_badge.short_description = "Discovery"
    discovery_source_badge.admin_order_field = "discovery_source"

    def extracted_data_formatted(self, obj):
        """Display extracted data as formatted JSON."""
        if obj.extracted_data:
            formatted = json.dumps(obj.extracted_data, indent=2)
            return format_html(
                '<pre style="white-space: pre-wrap; word-wrap: break-word; '
                'background: #f5f5f5; padding: 10px; border-radius: 4px; '
                'max-height: 400px; overflow-y: auto;">{}</pre>',
                formatted
            )
        return "-"
    extracted_data_formatted.short_description = "Extracted Data"

    def enriched_data_formatted(self, obj):
        """Display enriched data as formatted JSON."""
        if obj.enriched_data:
            formatted = json.dumps(obj.enriched_data, indent=2)
            return format_html(
                '<pre style="white-space: pre-wrap; word-wrap: break-word; '
                'background: #f5f5f5; padding: 10px; border-radius: 4px; '
                'max-height: 400px; overflow-y: auto;">{}</pre>',
                formatted
            )
        return "-"
    enriched_data_formatted.short_description = "Enriched Data"

    def awards_formatted(self, obj):
        """Display awards as formatted JSON."""
        if obj.awards:
            formatted = json.dumps(obj.awards, indent=2)
            return format_html(
                '<pre style="white-space: pre-wrap; word-wrap: break-word; '
                'background: #f5f5f5; padding: 10px; border-radius: 4px;">{}</pre>',
                formatted
            )
        return "-"
    awards_formatted.short_description = "Awards"

    @admin.action(description="Approve selected products")
    def approve_products(self, request, queryset):
        """Approve selected products."""
        count = 0
        for product in queryset.filter(status="pending"):
            product.approve(reviewer=request.user.username)
            count += 1
        self.message_user(request, f"Approved {count} product(s).")

    @admin.action(description="Reject selected products")
    def reject_products(self, request, queryset):
        """Reject selected products."""
        count = 0
        for product in queryset.filter(status="pending"):
            product.reject(reviewer=request.user.username)
            count += 1
        self.message_user(request, f"Rejected {count} product(s).")

    @admin.action(description="Mark as duplicate")
    def mark_duplicate(self, request, queryset):
        """Mark selected products as duplicates."""
        count = 0
        for product in queryset:
            product.mark_duplicate()
            count += 1
        self.message_user(request, f"Marked {count} product(s) as duplicate.")


@admin.register(CrawlerKeyword)
class CrawlerKeywordAdmin(admin.ModelAdmin):
    """
    Admin interface for crawler keywords.

    Task 8.7: Keyword management with search triggers.
    """

    list_display = [
        "keyword",
        "search_context",
        "product_types_display",
        "is_active_badge",
        "priority",
        "last_searched_at",
    ]
    list_filter = [
        "is_active",
        "search_context",
    ]
    search_fields = ["keyword", "notes"]
    readonly_fields = [
        "id",
        "last_searched_at",
        "next_search_at",
        "total_results_found",
        "created_at",
        "updated_at",
    ]
    ordering = ["-priority", "keyword"]

    fieldsets = (
        ("Keyword Configuration", {
            "fields": ("keyword", "product_types", "search_context"),
        }),
        ("Search Settings", {
            "fields": ("is_active", "priority", "search_frequency_hours"),
        }),
        ("Tracking", {
            "fields": ("last_searched_at", "next_search_at", "total_results_found"),
        }),
        ("Metadata", {
            "fields": ("notes", "created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )

    actions = ["trigger_search", "enable_keywords", "disable_keywords"]

    def product_types_display(self, obj):
        """Display product types as comma-separated list."""
        if obj.product_types:
            return ", ".join(obj.product_types)
        return "-"
    product_types_display.short_description = "Product Types"

    def is_active_badge(self, obj):
        """Display active status as colored badge."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; '
                'padding: 2px 8px; border-radius: 4px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; '
            'padding: 2px 8px; border-radius: 4px;">Inactive</span>'
        )
    is_active_badge.short_description = "Active"
    is_active_badge.admin_order_field = "is_active"

    @admin.action(description="Trigger search now")
    def trigger_search(self, request, queryset):
        """Trigger immediate search for selected keywords."""
        count = queryset.filter(is_active=True).update(next_search_at=timezone.now())
        self.message_user(request, f"Scheduled search for {count} keyword(s).")

    @admin.action(description="Disable selected keywords")
    def disable_keywords(self, request, queryset):
        """Disable selected keywords."""
        count = queryset.update(is_active=False)
        self.message_user(request, f"Disabled {count} keyword(s).")

    @admin.action(description="Enable selected keywords")
    def enable_keywords(self, request, queryset):
        """Enable selected keywords."""
        count = queryset.update(is_active=True)
        self.message_user(request, f"Enabled {count} keyword(s).")


@admin.register(CrawledURL)
class CrawledURLAdmin(admin.ModelAdmin):
    """Admin interface for crawled URLs."""

    list_display = [
        "url_truncated",
        "source",
        "is_product_page",
        "was_processed",
        "content_changed",
        "last_crawled_at",
    ]
    list_filter = [
        "is_product_page",
        "was_processed",
        "content_changed",
        "source",
    ]
    search_fields = ["url", "url_hash"]
    readonly_fields = [
        "id",
        "url",
        "url_hash",
        "content_hash",
        "first_seen_at",
        "last_crawled_at",
    ]
    ordering = ["-last_crawled_at"]

    def url_truncated(self, obj):
        """Display truncated URL."""
        max_length = 60
        if len(obj.url) > max_length:
            return obj.url[:max_length] + "..."
        return obj.url
    url_truncated.short_description = "URL"


@admin.register(CrawledArticle)
class CrawledArticleAdmin(admin.ModelAdmin):
    """Admin interface for crawled articles (skeleton model)."""

    list_display = [
        "title_truncated",
        "source",
        "author",
        "published_date",
        "is_original_live",
        "discovered_at",
    ]
    list_filter = [
        "source",
        "is_original_live",
        ("published_date", admin.DateFieldListFilter),
    ]
    search_fields = ["title", "original_url", "author"]
    readonly_fields = [
        "id",
        "discovered_at",
    ]
    ordering = ["-discovered_at"]

    def title_truncated(self, obj):
        """Display truncated title."""
        title = obj.title or obj.original_url
        if len(title) > 60:
            return title[:60] + "..."
        return title
    title_truncated.short_description = "Title"


# ============================================================
# Task Group 21: ProductAvailability Admin
# ============================================================


@admin.register(ProductAvailability)
class ProductAvailabilityAdmin(admin.ModelAdmin):
    """
    Task Group 21: Admin interface for product availability records.

    Displays availability across retailers with stock status badges,
    price information, and filtering by stock level.
    """

    list_display = [
        "product_name",
        "retailer",
        "retailer_country",
        "stock_level_badge",
        "price_display",
        "price_usd_display",
        "price_changed_badge",
        "last_checked",
    ]
    list_filter = [
        "stock_level",
        "in_stock",
        "price_changed",
        "retailer_country",
        ("last_checked", admin.DateFieldListFilter),
    ]
    search_fields = [
        "retailer",
        "retailer_url",
        "product__extracted_data",
    ]
    readonly_fields = [
        "id",
        "product",
        "retailer",
        "retailer_url",
        "retailer_country",
        "in_stock",
        "stock_level",
        "price",
        "currency",
        "price_usd",
        "price_eur",
        "last_checked",
        "price_changed",
        "previous_price",
    ]
    ordering = ["-last_checked"]

    fieldsets = (
        ("Product", {
            "fields": ("id", "product"),
        }),
        ("Retailer Information", {
            "fields": ("retailer", "retailer_url", "retailer_country"),
        }),
        ("Stock Status", {
            "fields": ("in_stock", "stock_level"),
        }),
        ("Pricing", {
            "fields": (
                "price",
                "currency",
                "price_usd",
                "price_eur",
            ),
        }),
        ("Price Change Tracking", {
            "fields": ("price_changed", "previous_price"),
        }),
        ("Tracking", {
            "fields": ("last_checked",),
        }),
    )

    def product_name(self, obj):
        """Display product name from extracted data."""
        if obj.product:
            name = obj.product.extracted_data.get("name", "Unknown")
            if len(name) > 40:
                return name[:40] + "..."
            return name
        return "-"
    product_name.short_description = "Product"

    def stock_level_badge(self, obj):
        """Display stock level as colored badge."""
        colors = {
            "in_stock": "#28a745",
            "low_stock": "#ffc107",
            "out_of_stock": "#dc3545",
            "pre_order": "#17a2b8",
            "discontinued": "#6c757d",
        }
        color = colors.get(obj.stock_level, "#6c757d")
        label = obj.stock_level.replace("_", " ").title()
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 4px;">{}</span>',
            color, label
        )
    stock_level_badge.short_description = "Stock"
    stock_level_badge.admin_order_field = "stock_level"

    def price_display(self, obj):
        """Display price with currency."""
        return f"{obj.currency} {obj.price:,.2f}"
    price_display.short_description = "Price"
    price_display.admin_order_field = "price"

    def price_usd_display(self, obj):
        """Display USD normalized price."""
        if obj.price_usd:
            return f"${obj.price_usd:,.2f}"
        return "-"
    price_usd_display.short_description = "Price (USD)"
    price_usd_display.admin_order_field = "price_usd"

    def price_changed_badge(self, obj):
        """Display price changed status as badge."""
        if obj.price_changed:
            return format_html(
                '<span style="background-color: #fd7e14; color: white; '
                'padding: 2px 8px; border-radius: 4px;">Changed</span>'
            )
        return format_html(
            '<span style="background-color: #6c757d; color: white; '
            'padding: 2px 8px; border-radius: 4px;">No Change</span>'
        )
    price_changed_badge.short_description = "Price Change"
    price_changed_badge.admin_order_field = "price_changed"

    def has_add_permission(self, request):
        """Disable manual availability creation (populated by crawler)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing availability (read-only from crawler)."""
        return False


# ============================================================
# Task Group 22: CategoryInsight Admin
# ============================================================


@admin.register(CategoryInsight)
class CategoryInsightAdmin(admin.ModelAdmin):
    """
    Task Group 22: Admin interface for category market insights.
    """

    list_display = [
        "category_display",
        "product_type",
        "sub_category",
        "trending_direction_badge",
        "total_products",
        "products_with_awards",
        "avg_price_usd_display",
        "avg_rating_display",
        "updated_at",
    ]
    list_filter = [
        "product_type",
        "sub_category",
        "trending_direction",
        "country",
    ]
    search_fields = [
        "product_type",
        "sub_category",
        "region",
        "country",
    ]
    readonly_fields = [
        "id",
        "updated_at",
    ]
    ordering = ["-updated_at"]

    def category_display(self, obj):
        """Display full category path."""
        parts = [obj.product_type, obj.sub_category]
        if obj.region:
            parts.append(obj.region)
        if obj.country:
            parts.append(obj.country)
        return " / ".join(parts)
    category_display.short_description = "Category"

    def trending_direction_badge(self, obj):
        """Display trending direction as colored badge."""
        colors = {
            "hot": "#dc3545",
            "rising": "#28a745",
            "stable": "#6c757d",
            "declining": "#ffc107",
            "cold": "#17a2b8",
        }
        color = colors.get(obj.trending_direction, "#6c757d")
        label = obj.trending_direction.title()
        return format_html(
            '<span style="background-color: {}; color: white; '
            'padding: 2px 8px; border-radius: 4px;">{}</span>',
            color, label
        )
    trending_direction_badge.short_description = "Trend"
    trending_direction_badge.admin_order_field = "trending_direction"

    def avg_price_usd_display(self, obj):
        """Display average USD price formatted."""
        return f"${obj.avg_price_usd:,.2f}"
    avg_price_usd_display.short_description = "Avg Price (USD)"
    avg_price_usd_display.admin_order_field = "avg_price_usd"

    def avg_rating_display(self, obj):
        """Display average rating."""
        if obj.avg_rating:
            return f"{obj.avg_rating:.1f}"
        return "-"
    avg_rating_display.short_description = "Avg Rating"
    avg_rating_display.admin_order_field = "avg_rating"


# ============================================================
# Task Group 23: PurchaseRecommendation Admin
# ============================================================


@admin.register(PurchaseRecommendation)
class PurchaseRecommendationAdmin(admin.ModelAdmin):
    """
    Task Group 23: Admin interface for purchase recommendations.
    """

    list_display = [
        "product_name",
        "recommendation_tier",
        "recommendation_score",
        "is_active",
        "created_at",
    ]
    list_filter = [
        "recommendation_tier",
        "is_active",
        ("created_at", admin.DateFieldListFilter),
    ]
    ordering = ["-recommendation_score", "-created_at"]

    def product_name(self, obj):
        """Display product name from extracted data."""
        if obj.product:
            name = obj.product.extracted_data.get("name", "Unknown")
            if len(name) > 40:
                return name[:40] + "..."
            return name
        return "-"
    product_name.short_description = "Product"


# ============================================================
# Task Group 24: ShopInventory Admin
# ============================================================


@admin.register(ShopInventory)
class ShopInventoryAdmin(admin.ModelAdmin):
    """
    Task Group 24: Admin interface for shop inventory management.
    """

    list_display = [
        "product_name",
        "product_type",
        "current_stock",
        "reorder_point",
        "is_active",
    ]
    list_filter = [
        "product_type",
        "is_active",
    ]
    search_fields = ["product_name"]
    ordering = ["product_name"]


# ============================================================
# Task Group 26: CrawlerMetrics Admin
# ============================================================


@admin.register(CrawlerMetrics)
class CrawlerMetricsAdmin(admin.ModelAdmin):
    """
    Task Group 26: Admin interface for crawler metrics.
    """

    list_display = [
        "date",
        "pages_crawled",
        "products_extracted",
        "queue_depth",
    ]
    list_filter = [
        ("date", admin.DateFieldListFilter),
    ]
    ordering = ["-date"]

    def has_add_permission(self, request):
        """Disable manual metrics creation (populated by system)."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing metrics (read-only from system)."""
        return False


# ============================================================
# New Models Admin Registration
# ============================================================


@admin.register(DiscoveredBrand)
class DiscoveredBrandAdmin(admin.ModelAdmin):
    """Admin interface for discovered brands."""

    list_display = [
        "name",
        "country",
        "region",
        "product_count",
        "award_count",
        "created_at",
    ]
    list_filter = [
        "country",
    ]
    search_fields = ["name", "country", "region"]
    prepopulated_fields = {"slug": ("name",)}
    ordering = ["name"]


@admin.register(WhiskeyDetails)
class WhiskeyDetailsAdmin(admin.ModelAdmin):
    """Admin interface for whiskey details."""

    list_display = [
        "product",
        "whiskey_type",
        "whiskey_country",
        "whiskey_region",
        "distillery",
    ]
    list_filter = [
        "whiskey_type",
        "whiskey_country",
    ]
    search_fields = ["distillery", "whiskey_region"]


@admin.register(PortWineDetails)
class PortWineDetailsAdmin(admin.ModelAdmin):
    """Admin interface for port wine details."""

    list_display = [
        "product",
        "style",
        "producer_house",
        "harvest_year",
    ]
    list_filter = [
        "style",
    ]
    search_fields = ["producer_house", "quinta"]


@admin.register(ProductAward)
class ProductAwardAdmin(admin.ModelAdmin):
    """Admin interface for product awards."""

    list_display = [
        "product",
        "competition",
        "year",
        "medal",
        "award_category",
    ]
    list_filter = [
        "medal",
        "year",
        "competition",
    ]
    search_fields = ["competition", "award_category"]
    ordering = ["-year"]


@admin.register(BrandAward)
class BrandAwardAdmin(admin.ModelAdmin):
    """Admin interface for brand awards."""

    list_display = [
        "brand",
        "competition",
        "year",
        "medal",
        "award_category",
    ]
    list_filter = [
        "medal",
        "year",
        "competition",
    ]
    search_fields = ["competition", "award_category"]
    ordering = ["-year"]


@admin.register(ProductPrice)
class ProductPriceAdmin(admin.ModelAdmin):
    """Admin interface for product prices."""

    list_display = [
        "product",
        "retailer",
        "price",
        "currency",
        "in_stock",
        "date_observed",
    ]
    list_filter = [
        "currency",
        "in_stock",
        "retailer_country",
    ]
    search_fields = ["retailer"]
    ordering = ["-date_observed"]


@admin.register(ProductRating)
class ProductRatingAdmin(admin.ModelAdmin):
    """Admin interface for product ratings."""

    list_display = [
        "product",
        "source",
        "score",
        "max_score",
        "updated_at",
    ]
    list_filter = [
        "source",
    ]
    search_fields = ["source", "reviewer"]
    ordering = ["-updated_at"]


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    """Admin interface for product images."""

    list_display = [
        "product",
        "image_type",
        "source",
        "is_primary",
    ]
    list_filter = [
        "image_type",
        "is_primary",
    ]
    search_fields = ["source"]


@admin.register(ProductSource)
class ProductSourceAdmin(admin.ModelAdmin):
    """Admin interface for product sources junction table."""

    list_display = [
        "product",
        "source",
        "extraction_confidence",
        "mention_count",
        "extracted_at",
    ]
    list_filter = [
        "extraction_confidence",
    ]
    ordering = ["-extracted_at"]


@admin.register(BrandSource)
class BrandSourceAdmin(admin.ModelAdmin):
    """Admin interface for brand sources junction table."""

    list_display = [
        "brand",
        "source",
        "extraction_confidence",
        "mention_count",
        "extracted_at",
    ]
    list_filter = [
        "extraction_confidence",
    ]
    ordering = ["-extracted_at"]


@admin.register(ProductFieldSource)
class ProductFieldSourceAdmin(admin.ModelAdmin):
    """Admin interface for product field sources."""

    list_display = [
        "product",
        "field_name",
        "source",
        "confidence",
        "extracted_at",
    ]
    list_filter = [
        "field_name",
        "confidence",
    ]
    search_fields = ["field_name"]
    ordering = ["-extracted_at"]


@admin.register(ProductCandidate)
class ProductCandidateAdmin(admin.ModelAdmin):
    """Admin interface for product candidates."""

    list_display = [
        "raw_name",
        "match_status",
        "match_confidence",
        "match_method",
        "matched_product",
        "created_at",
    ]
    list_filter = [
        "match_status",
        "match_method",
    ]
    search_fields = ["raw_name", "normalized_name"]
    ordering = ["-created_at"]


@admin.register(CrawlSchedule)
class CrawlScheduleAdmin(admin.ModelAdmin):
    """Admin interface for crawl schedules."""

    list_display = [
        "source",
        "next_run",
        "last_run",
        "last_status",
        "consecutive_errors",
        "is_active",
    ]
    list_filter = [
        "is_active",
        "last_status",
    ]
    ordering = ["next_run"]


@admin.register(PriceHistory)
class PriceHistoryAdmin(admin.ModelAdmin):
    """Admin interface for price history."""

    list_display = [
        "product",
        "retailer",
        "price",
        "currency",
        "observed_at",
    ]
    list_filter = [
        "currency",
        "retailer_country",
    ]
    search_fields = ["retailer"]
    ordering = ["-observed_at"]


@admin.register(PriceAlert)
class PriceAlertAdmin(admin.ModelAdmin):
    """Admin interface for price alerts."""

    list_display = [
        "product",
        "alert_type",
        "triggered_value",
        "retailer",
        "acknowledged",
        "created_at",
    ]
    list_filter = [
        "alert_type",
        "acknowledged",
    ]
    ordering = ["-created_at"]


@admin.register(NewRelease)
class NewReleaseAdmin(admin.ModelAdmin):
    """Admin interface for new releases."""

    list_display = [
        "name",
        "brand",
        "product_type",
        "release_status",
        "expected_release_date",
        "limited_edition",
        "is_tracked",
    ]
    list_filter = [
        "release_status",
        "product_type",
        "limited_edition",
        "is_tracked",
    ]
    search_fields = ["name"]
    ordering = ["-expected_release_date"]
