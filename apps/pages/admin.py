from django.contrib import admin

from .models import Page


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ("title", "site", "status", "page_type", "enable", "created_at")
    list_filter = ("status", "page_type", "enable")
    search_fields = ("title", "slug", "site__name")
    readonly_fields = ("slug", "created_at", "updated_at", "created_by", "updated_by")
    ordering = ("-created_at",)
