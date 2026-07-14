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

    def validate_name(self, value):
        request = self.context.get("request")
        queryset = Site.objects.filter(user=request.user, name=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("You already have a site with this name.")
        return value
    