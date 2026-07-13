from rest_framework import serializers
from .models import Site


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = [
            "id", "user", "name", "status",
            "favicon", "logo", "global_css",
            "created_at", "updated_at", "updated_by",
        ]
        read_only_fields = ["id", "user", "updated_by", "created_at", "updated_at"]