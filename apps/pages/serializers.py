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
        read_only_fields = ["id", "slug", "created_by", "updated_by", "created_at", "updated_at"]

        def validate_site(self, value):
            request = self.context.get("request")
            if request.user != value.user:
                raise serializers.ValidationError("You can only add pages to your own site.")
            return value
