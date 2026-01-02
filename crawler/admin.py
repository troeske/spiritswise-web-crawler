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
    # Discovery models
    SearchTerm,
    DiscoverySchedule,
    DiscoveryJob,
    DiscoveryResult,
    QuotaUsage,
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
    """Admin interface for unified crawl schedules."""

    list_display = [
        "name",
        "category",
        "frequency",
        "is_active",
        "priority",
        "next_run",
        "last_run",
        "total_runs",
        "products_stats",
    ]

    list_filter = [
        "category",
        "frequency",
        "is_active",
        "product_types",
    ]

    search_fields = ["name", "slug", "search_terms"]

    readonly_fields = [
        "id",
        "created_at",
        "updated_at",
        "total_runs",
        "total_products_found",
        "total_products_new",
        "total_products_duplicate",
        "total_errors",
    ]

    fieldsets = [
        ("Identity", {
            "fields": ["name", "slug", "description", "category"],
        }),
        ("Scheduling", {
            "fields": ["is_active", "frequency", "priority", "next_run", "last_run"],
        }),
        ("Search Configuration", {
            "fields": ["search_terms", "max_results_per_term"],
        }),
        ("Filtering", {
            "fields": ["product_types", "exclude_domains"],
        }),
        ("Competition Settings", {
            "fields": ["base_url", "robots_txt_compliant", "tos_compliant"],
            "classes": ["collapse"],
        }),
        ("Quotas", {
            "fields": ["daily_quota", "monthly_quota"],
        }),
        ("Statistics", {
            "fields": [
                "total_runs",
                "total_products_found",
                "total_products_new",
                "total_products_duplicate",
                "total_errors",
            ],
            "classes": ["collapse"],
        }),
        ("Metadata", {
            "fields": ["id", "created_at", "updated_at", "config"],
            "classes": ["collapse"],
        }),
    ]

    actions = ["run_now", "activate", "deactivate"]
    ordering = ["-priority", "name"]

    @admin.display(description="Products (New/Dup/Total)")
    def products_stats(self, obj):
        return f"{obj.total_products_new}/{obj.total_products_duplicate}/{obj.total_products_found}"

    @admin.action(description="Run selected schedules now")
    def run_now(self, request, queryset):
        from crawler.tasks import trigger_scheduled_job_manual

        count = 0
        for schedule in queryset:
            trigger_scheduled_job_manual.delay(str(schedule.id))
            count += 1

        self.message_user(request, f"Triggered {count} schedule(s)")

    @admin.action(description="Activate selected schedules")
    def activate(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="Deactivate selected schedules")
    def deactivate(self, request, queryset):
        queryset.update(is_active=False)


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


# =============================================================================
# Discovery System Admin
# Task Group: Generic Search Discovery Flow
# =============================================================================


class DiscoveryResultInline(admin.TabularInline):
    """Inline display of discovery results within a job."""

    model = DiscoveryResult
    extra = 0
    readonly_fields = [
        "search_term",
        "source_url",
        "source_type",
        "name_match_score",
        "status",
        "product_link",
        "created_at",
    ]
    fields = [
        "search_term",
        "source_url",
        "source_type",
        "name_match_score",
        "status",
        "product_link",
    ]
    can_delete = False
    max_num = 0

    def product_link(self, obj):
        """Link to the discovered product if any."""
        if obj.product:
            url = f"/admin/crawler/discoveredproduct/{obj.product.id}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.product.name[:50])
        return "-"

    product_link.short_description = "Product"


@admin.register(SearchTerm)
class SearchTermAdmin(admin.ModelAdmin):
    """
    Admin interface for search terms.

    Allows configuration of search terms used for product discovery.
    Supports inline editing for quick priority adjustments.
    """

    list_display = [
        "term_template",
        "category",
        "product_type",
        "priority",
        "is_active_badge",
        "seasonal_display",
        "search_count",
        "products_discovered",
        "success_rate",
        "last_searched",
    ]
    list_filter = [
        "is_active",
        "category",
        "product_type",
        ("last_searched", admin.EmptyFieldListFilter),
    ]
    list_editable = [
        "priority",
    ]
    search_fields = ["term_template"]
    ordering = ["-priority", "category", "term_template"]
    readonly_fields = [
        "search_count",
        "products_discovered",
        "last_searched",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Search Term Configuration",
            {
                "fields": (
                    "term_template",
                    "category",
                    "product_type",
                    "priority",
                    "is_active",
                ),
            },
        ),
        (
            "Seasonal Settings",
            {
                "fields": (
                    "seasonal_start_month",
                    "seasonal_end_month",
                ),
                "classes": ("collapse",),
                "description": "Leave blank for year-round terms. For wrapping ranges (e.g., Nov-Feb), the system handles it automatically.",
            },
        ),
        (
            "Statistics (Read-Only)",
            {
                "fields": (
                    "search_count",
                    "products_discovered",
                    "last_searched",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["activate_terms", "deactivate_terms", "reset_statistics"]

    def is_active_badge(self, obj):
        """Display active status as colored badge."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">Inactive</span>'
        )

    is_active_badge.short_description = "Status"

    def seasonal_display(self, obj):
        """Display seasonal range if set."""
        if obj.seasonal_start_month and obj.seasonal_end_month:
            months = [
                "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
            ]
            start = months[obj.seasonal_start_month - 1]
            end = months[obj.seasonal_end_month - 1]
            in_season = obj.is_in_season()
            color = "#28a745" if in_season else "#6c757d"
            return format_html(
                '<span style="color: {};">{} - {}</span>',
                color, start, end
            )
        return "-"

    seasonal_display.short_description = "Season"

    def success_rate(self, obj):
        """Calculate and display success rate."""
        if obj.search_count > 0:
            rate = (obj.products_discovered / obj.search_count) * 100
            color = "#28a745" if rate >= 50 else "#ffc107" if rate >= 20 else "#dc3545"
            return format_html(
                '<span style="color: {};">{:.1f}%</span>',
                color, rate
            )
        return "-"

    success_rate.short_description = "Success Rate"

    @admin.action(description="Activate selected search terms")
    def activate_terms(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"Activated {count} search term(s).")

    @admin.action(description="Deactivate selected search terms")
    def deactivate_terms(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {count} search term(s).")

    @admin.action(description="Reset statistics for selected terms")
    def reset_statistics(self, request, queryset):
        count = queryset.update(search_count=0, products_discovered=0, last_searched=None)
        self.message_user(request, f"Reset statistics for {count} search term(s).")


@admin.register(DiscoverySchedule)
class DiscoveryScheduleAdmin(admin.ModelAdmin):
    """
    Admin interface for discovery schedules.

    Allows configuration of automated discovery job schedules with
    a "Run Now" action for manual triggering.
    """

    list_display = [
        "name",
        "frequency",
        "run_at_hour_display",
        "is_active_badge",
        "max_search_terms",
        "max_results_per_term",
        "filter_summary",
        "last_run",
        "next_run",
    ]
    list_filter = [
        "is_active",
        "frequency",
    ]
    search_fields = ["name"]
    ordering = ["-is_active", "name"]
    readonly_fields = [
        "last_run",
        "next_run",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Schedule Configuration",
            {
                "fields": (
                    "name",
                    "frequency",
                    "run_at_hour",
                    "is_active",
                ),
            },
        ),
        (
            "Job Limits",
            {
                "fields": (
                    "max_search_terms",
                    "max_results_per_term",
                ),
            },
        ),
        (
            "Filters",
            {
                "fields": (
                    "search_categories",
                    "product_types",
                ),
                "description": "Leave empty to include all categories/product types.",
            },
        ),
        (
            "Run History",
            {
                "fields": (
                    "last_run",
                    "next_run",
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    actions = ["run_schedule_now", "run_discovery_now", "activate_schedules", "deactivate_schedules"]

    def is_active_badge(self, obj):
        """Display active status as colored badge."""
        if obj.is_active:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 8px; '
                'border-radius: 3px; font-size: 11px;">Active</span>'
            )
        return format_html(
            '<span style="background-color: #dc3545; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">Inactive</span>'
        )

    is_active_badge.short_description = "Status"

    def run_at_hour_display(self, obj):
        """Display run hour in 12-hour format."""
        hour = obj.run_at_hour
        if hour == 0:
            return "12:00 AM"
        elif hour < 12:
            return f"{hour}:00 AM"
        elif hour == 12:
            return "12:00 PM"
        else:
            return f"{hour - 12}:00 PM"

    run_at_hour_display.short_description = "Run At"

    def filter_summary(self, obj):
        """Display summary of filters."""
        parts = []
        if obj.search_categories:
            parts.append(f"{len(obj.search_categories)} categories")
        if obj.product_types:
            parts.append(f"{len(obj.product_types)} types")
        return ", ".join(parts) if parts else "All"

    filter_summary.short_description = "Filters"

    @admin.action(description="Run selected schedules now")
    def run_schedule_now(self, request, queryset):
        """Create and queue discovery jobs for selected schedules."""
        from crawler.tasks import trigger_discovery_job_manual

        jobs_dispatched = 0
        for schedule in queryset:
            try:
                # Dispatch Celery task
                trigger_discovery_job_manual.apply_async(
                    args=[str(schedule.id)],
                    queue="discovery",
                )
                jobs_dispatched += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Failed to dispatch job for {schedule.name}: {e}",
                    level="ERROR"
                )

        self.message_user(
            request,
            f"Dispatched {jobs_dispatched} discovery job(s)."
        )

    @admin.action(description="Run discovery now")
    def run_discovery_now(self, request, queryset):
        """Alias for run_schedule_now for backward compatibility."""
        return self.run_schedule_now(request, queryset)

    @admin.action(description="Activate selected schedules")
    def activate_schedules(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f"Activated {count} schedule(s).")

    @admin.action(description="Deactivate selected schedules")
    def deactivate_schedules(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {count} schedule(s).")


@admin.register(DiscoveryJob)
class DiscoveryJobAdmin(admin.ModelAdmin):
    """
    Admin interface for discovery jobs.

    Provides read-only view of job progress with metrics display.
    """

    list_display = [
        "id_short",
        "schedule_name",
        "status_badge",
        "progress_display",
        "urls_found",
        "products_new",
        "api_calls_display",
        "duration_display",
        "started_at",
    ]
    list_filter = [
        "status",
        ("schedule", admin.RelatedOnlyFieldListFilter),
    ]
    ordering = ["-started_at"]
    readonly_fields = [
        "id",
        "schedule",
        "status",
        "started_at",
        "completed_at",
        "search_terms_processed",
        "search_terms_total",
        "urls_found",
        "urls_crawled",
        "urls_skipped",
        "products_found",
        "products_new",
        "products_updated",
        "products_duplicates",
        "products_failed",
        "products_needs_review",
        "serpapi_calls_used",
        "scrapingbee_calls_used",
        "ai_calls_used",
        "error_count",
        "error_log",
    ]
    inlines = [DiscoveryResultInline]

    fieldsets = (
        (
            "Job Info",
            {
                "fields": (
                    "id",
                    "schedule",
                    "status",
                    "started_at",
                    "completed_at",
                ),
            },
        ),
        (
            "Search Terms Progress",
            {
                "fields": (
                    "search_terms_processed",
                    "search_terms_total",
                ),
            },
        ),
        (
            "URLs Progress",
            {
                "fields": (
                    "urls_found",
                    "urls_crawled",
                    "urls_skipped",
                ),
            },
        ),
        (
            "Products Progress",
            {
                "fields": (
                    "products_found",
                    "products_new",
                    "products_updated",
                    "products_duplicates",
                    "products_failed",
                    "products_needs_review",
                ),
            },
        ),
        (
            "API Usage",
            {
                "fields": (
                    "serpapi_calls_used",
                    "scrapingbee_calls_used",
                    "ai_calls_used",
                ),
            },
        ),
        (
            "Errors",
            {
                "fields": (
                    "error_count",
                    "error_log",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        """Disable manual job creation - use schedules."""
        return False

    def has_change_permission(self, request, obj=None):
        """Jobs are read-only."""
        return False

    def id_short(self, obj):
        """Display shortened UUID."""
        return str(obj.id)[:8]

    id_short.short_description = "ID"

    def schedule_name(self, obj):
        """Display schedule name or 'Manual'."""
        return obj.schedule.name if obj.schedule else "Manual"

    schedule_name.short_description = "Schedule"

    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            "pending": "#6c757d",
            "running": "#007bff",
            "completed": "#28a745",
            "failed": "#dc3545",
            "cancelled": "#ffc107",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.status.title()
        )

    status_badge.short_description = "Status"

    def progress_display(self, obj):
        """Display progress as fraction."""
        if obj.search_terms_total > 0:
            pct = (obj.search_terms_processed / obj.search_terms_total) * 100
            return f"{obj.search_terms_processed}/{obj.search_terms_total} ({pct:.0f}%)"
        return "-"

    progress_display.short_description = "Progress"

    def api_calls_display(self, obj):
        """Display API call summary."""
        return f"S:{obj.serpapi_calls_used} B:{obj.scrapingbee_calls_used} A:{obj.ai_calls_used}"

    api_calls_display.short_description = "API Calls (Serp/Bee/AI)"

    def duration_display(self, obj):
        """Display job duration."""
        if obj.started_at and obj.completed_at:
            duration = obj.completed_at - obj.started_at
            total_seconds = int(duration.total_seconds())
            minutes, seconds = divmod(total_seconds, 60)
            if minutes > 0:
                return f"{minutes}m {seconds}s"
            return f"{seconds}s"
        elif obj.started_at:
            return "Running..."
        return "-"

    duration_display.short_description = "Duration"


@admin.register(DiscoveryResult)
class DiscoveryResultAdmin(admin.ModelAdmin):
    """
    Admin interface for individual discovery results.

    Provides detailed view of each URL discovered and processed.
    """

    list_display = [
        "id_short",
        "job_id_short",
        "search_term_display",
        "source_url_truncated",
        "source_type",
        "name_match_score_display",
        "status_badge",
        "product_link",
        "created_at",
    ]
    list_filter = [
        "status",
        "source_type",
        ("product", admin.EmptyFieldListFilter),
    ]
    search_fields = ["source_url", "search_term__term_template"]
    ordering = ["-created_at"]
    readonly_fields = [
        "id",
        "job",
        "search_term",
        "source_url",
        "source_type",
        "name_match_score",
        "status",
        "product",
        "extracted_data",
        "error_message",
        "created_at",
    ]

    fieldsets = (
        (
            "Result Info",
            {
                "fields": (
                    "id",
                    "job",
                    "search_term",
                    "status",
                ),
            },
        ),
        (
            "Source",
            {
                "fields": (
                    "source_url",
                    "source_type",
                    "name_match_score",
                ),
            },
        ),
        (
            "Product",
            {
                "fields": ("product",),
            },
        ),
        (
            "Extracted Data",
            {
                "fields": ("extracted_data",),
                "classes": ("collapse",),
            },
        ),
        (
            "Error",
            {
                "fields": ("error_message",),
                "classes": ("collapse",),
            },
        ),
    )

    def has_add_permission(self, request):
        """Disable manual result creation."""
        return False

    def has_change_permission(self, request, obj=None):
        """Results are read-only."""
        return False

    def id_short(self, obj):
        """Display shortened UUID."""
        return str(obj.id)[:8]

    id_short.short_description = "ID"

    def job_id_short(self, obj):
        """Display shortened job UUID."""
        return str(obj.job_id)[:8] if obj.job_id else "-"

    job_id_short.short_description = "Job"

    def search_term_display(self, obj):
        """Display search term template."""
        if obj.search_term:
            return obj.search_term.term_template[:30]
        return "-"

    search_term_display.short_description = "Search Term"

    def source_url_truncated(self, obj):
        """Display truncated URL with link."""
        if obj.source_url:
            truncated = obj.source_url[:50] + "..." if len(obj.source_url) > 50 else obj.source_url
            return format_html('<a href="{}" target="_blank">{}</a>', obj.source_url, truncated)
        return "-"

    source_url_truncated.short_description = "Source URL"

    def name_match_score_display(self, obj):
        """Display score with color coding."""
        score = obj.name_match_score
        if score >= 0.8:
            color = "#28a745"
        elif score >= 0.6:
            color = "#ffc107"
        else:
            color = "#dc3545"
        return format_html('<span style="color: {};">{:.2f}</span>', color, score)

    name_match_score_display.short_description = "Match Score"

    def status_badge(self, obj):
        """Display status as colored badge."""
        colors = {
            "pending": "#6c757d",
            "processing": "#007bff",
            "success": "#28a745",
            "failed": "#dc3545",
            "skipped": "#ffc107",
        }
        color = colors.get(obj.status, "#6c757d")
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; '
            'border-radius: 3px; font-size: 11px;">{}</span>',
            color, obj.status.title()
        )

    status_badge.short_description = "Status"

    def product_link(self, obj):
        """Link to the discovered product if any."""
        if obj.product:
            url = f"/admin/crawler/discoveredproduct/{obj.product.id}/change/"
            return format_html('<a href="{}">{}</a>', url, obj.product.name[:30])
        return "-"

    product_link.short_description = "Product"


@admin.register(QuotaUsage)
class QuotaUsageAdmin(admin.ModelAdmin):
    """
    Admin interface for API quota tracking.

    Phase 6: Displays current usage, limits, and remaining quota.
    """

    list_display = [
        "api_name",
        "month",
        "current_usage",
        "monthly_limit",
        "remaining_display",
        "usage_bar",
        "last_used",
    ]
    list_filter = [
        "api_name",
        "month",
    ]
    search_fields = ["api_name"]
    ordering = ["-month", "api_name"]
    readonly_fields = [
        "current_usage",
        "last_used",
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "API Information",
            {
                "fields": (
                    "api_name",
                    "month",
                ),
            },
        ),
        (
            "Usage",
            {
                "fields": (
                    "current_usage",
                    "monthly_limit",
                    "last_used",
                ),
            },
        ),
        (
            "Timestamps",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def remaining_display(self, obj):
        """Display remaining quota."""
        return obj.remaining

    remaining_display.short_description = "Remaining"

    def usage_bar(self, obj):
        """Display usage as a progress bar."""
        percentage = obj.usage_percentage
        if percentage >= 90:
            color = "#dc3545"  # Red
        elif percentage >= 70:
            color = "#ffc107"  # Yellow
        else:
            color = "#28a745"  # Green

        return format_html(
            '<div style="width: 100px; background-color: #e9ecef; border-radius: 3px;">'
            '<div style="width: {}%; height: 20px; background-color: {}; border-radius: 3px;"></div>'
            '</div>'
            '<span style="margin-left: 5px;">{:.1f}%</span>',
            min(percentage, 100), color, percentage
        )

    usage_bar.short_description = "Usage %"
