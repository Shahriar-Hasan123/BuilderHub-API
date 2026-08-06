from PIL import Image
from rest_framework import serializers

from apps.core.utils.image_field_processor import ImageFieldProcessor

from .models import Site, SiteImage, SitePublishVersion


class SiteSerializer(serializers.ModelSerializer):
    optimized_image_fields = {"favicon": 50, "logo": 50, "thumbnail": 50}
    name = serializers.CharField(required=True, allow_blank=False)

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
            "current_published_version",
            "created_by",
            "created_at",
            "updated_at",
            "updated_by",
        ]
        read_only_fields = [
            "id",
            "user",
            "current_published_version",
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


class SiteImageSerializer(serializers.ModelSerializer):
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
            "device",
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

    def create(self, validated_data):
        validated_data = ImageFieldProcessor().process(
            self.optimized_image_fields, validated_data
        )

        self.extract_image_metadata(validated_data)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = ImageFieldProcessor().process(
            self.optimized_image_fields, validated_data
        )

        self.extract_image_metadata(validated_data)

        return super().update(instance, validated_data)

    def extract_image_metadata(self, validated_data):
        image = validated_data.get("image")

        if not image:
            return

        # Generate filename only if user did not provide one
        if not validated_data.get("file_name"):
            validated_data["file_name"] = image.name

        # Always calculate file size
        validated_data["file_size"] = image.size

        # Always calculate dimensions
        try:
            with Image.open(image) as img:
                validated_data["width"] = img.width
                validated_data["height"] = img.height

        except Exception:
            pass


class SiteSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "name", "status", "url"]


class SitePublishVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SitePublishVersion
        fields = [
            "id",
            "version_number",
            "header_hash",
            "footer_hash",
            "page_hashes",
            "published_by",
            "created_at",
        ]
        read_only_fields = fields
