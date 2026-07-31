from django.utils.text import slugify
from rest_framework import serializers
from apps.core.utils.image_field_processor import ImageFieldProcessor

from apps.sites.serializers import SiteSummarySerializer

from .models import Page


class PageSerializer(serializers.ModelSerializer):
    optimized_image_fields = {"hero_image": 300}

    site = SiteSummarySerializer(read_only=True)

    class Meta:
        model = Page
        fields = [
            "id",
            "title",
            "slug",
            "meta_description",
            "status",
            "page_type",
            "enable",
            "canonical_url",
            "html",
            "css",
            "hero_image",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
            "site",
        ]
        read_only_fields = [
            "id",
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
    
    def create(self, validated_data):
        validated_data = ImageFieldProcessor().process(
            self.optimized_image_fields, validated_data
        )
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = ImageFieldProcessor().process(
            self.optimized_image_fields, validated_data
        )
        return super().update(instance, validated_data)
