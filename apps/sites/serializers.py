from rest_framework import serializers
from apps.core.mixins import ImageOptimizationMixin

from .models import Site


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


class SiteSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "name", "status", "url"]
