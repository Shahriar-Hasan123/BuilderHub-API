from django.utils.text import slugify
from rest_framework import serializers

from .models import Page


class PageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Page
        fields = [
            "id",
            "site",
            "title",
            "slug",
            "meta_description",
            "status",
            "page_type",
            "enable",
            "canonical_url",
            "html",
            "css",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "site",
            "slug",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_title(self, value):
        site = self.context.get("site")
        prospective_slug = slugify(value)
        queryset = Page.objects.filter(site=site, slug=prospective_slug)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError(
                "A page with this title already exists for this site."
            )
        return value
