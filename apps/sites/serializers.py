from rest_framework import serializers

from apps.core.mixins import ImageOptimizationMixin

from .models import Site, SiteImage


class SiteSerializer(ImageOptimizationMixin, serializers.ModelSerializer):
    optimized_image_fields = {"favicon": 50, "logo": 50, "thumbnail": 50}

    class Meta:
        model = Site
        fields = [
            "id",
            "user",
            "name",
            "url",
            "status",
            "favicon",
            "logo",
            "thumbnail",
            "global_css",
            "header",
            "footer",
            "created_by",
            "created_at",
            "updated_at",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "user",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_name(self, value):
        queryset = Site.objects.filter(name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("A site with this name already exists.")
        return value


class SiteImageSerializer(ImageOptimizationMixin, serializers.ModelSerializer):
    optimized_image_fields = {"image": 150}

    class Meta:
        model = SiteImage
        fields = [
            "id",
            "site",
            "page",
            "file_name",
            "image",
            "alt_text",
            "file_size",
            "width",
            "height",
            "created_by",
            "created_at",
            "updated_at",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "site",
            "file_size",
            "width",
            "height",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]

    def validate_page(self, value):
        site = self.context.get("site")
        if value and site and value.site_id != site.id:
            raise serializers.ValidationError("Page must belong to the requested site.")
        return value


class SiteSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "name", "status", "url"]
