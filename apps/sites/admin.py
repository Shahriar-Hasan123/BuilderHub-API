from django.contrib import admin

from .models import Site, SiteImage


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "status", "created_by", "updated_by", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    ordering = ("-created_at",)


@admin.register(SiteImage)
class SiteImageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "site",
        "page",
        "file_name",
        "created_by",
        "updated_by",
        "created_at",
    )
    list_filter = ("site", "page")
    search_fields = ("alt_text", "file_name", "site__name", "page__title")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    ordering = ("-created_at",)
