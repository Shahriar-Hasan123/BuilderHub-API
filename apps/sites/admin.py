from django.contrib import admin

from .models import Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "status", "created_by", "updated_by", "created_at")
    list_filter = ("status",)
    search_fields = ("name", "user__username", "user__email")
    readonly_fields = ("created_at", "updated_at", "created_by", "updated_by")
    ordering = ("-created_at",)
