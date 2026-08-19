# sites/serializers.py
from rest_framework import serializers
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.base import ContentFile

from apps.sites.services.optimization.optimizer import compress_image
from apps.sites.services.optimization.variations import generate_variants
from .models import ImageVariant, Site, SiteImage, SitePublishVersion

from apps.core.validators import (
    validate_upload_size,
    detect_format,
    is_animated,
    get_dimensions,
    validate_min_dimensions,
)

class SiteSerializer(serializers.ModelSerializer):
    current_published_version = serializers.SerializerMethodField()

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
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)

    def get_current_published_version(self, obj):
        v = getattr(obj, "current_published_version", None)
        return v.version_number if v else None


class ImageVariantSerializer(serializers.ModelSerializer):
    image_path = serializers.SerializerMethodField()

    class Meta:
        model = ImageVariant
        fields = [
            "id",
            "variant_type",
            "image_path",
            "width",
            "height",
            "format",
            "file_size",
        ]
        read_only_fields = fields

    def get_image_path(self, obj):
        return obj.image.url if obj.image else None


class SiteImageSerializer(serializers.ModelSerializer):
    # SVG is accepted by the custom validator and stored through the model's
    # existing ImageField without Pillow-based DRF validation.
    image = serializers.FileField(write_only=True)
    
    image_path = serializers.SerializerMethodField()
    file_size = serializers.SerializerMethodField()
    variants = ImageVariantSerializer(many=True, read_only=True)

    class Meta:
        model = SiteImage
        fields = [
            "id",
            "site",
            "page",
            "file_name",
            "image",
            "image_path",
            "variants",
            "image_type",
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
            "file_name",
            "file_size",
            "width",
            "height",
            "created_by",
            "updated_by",
            "created_at",
            "updated_at",
        ]
        
    def validate(self, attrs):
        image_file = attrs.get("image")
        image_type = attrs.get("image_type") or getattr(
            self.instance, "image_type", None
        )

        if image_file is None:
            return attrs

        try:
            validate_upload_size(image_file)
            fmt = detect_format(image_file)
            animated = is_animated(image_file, fmt)
            width, height = get_dimensions(image_file, fmt)
            validate_min_dimensions(width, height, image_type)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(str(exc))    
        
        # Stash for create() — avoids re-detecting format/animation a second time
        attrs["_fmt"] = fmt
        attrs["_animated"] = animated
        attrs["_width"] = width
        attrs["_height"] = height
        return attrs

    def validate_page(self, value):
        site = self.context.get("site")
        if value and site and value.site_id != site.id:
            raise serializers.ValidationError("Page must belong to the requested site.")
        return value


    def create(self, validated_data):
        image_file = validated_data["image"]
        image_type = validated_data["image_type"]
        fmt = validated_data.pop("_fmt")
        animated = validated_data.pop("_animated")
        source_width = validated_data.pop("_width", None)
        source_height = validated_data.pop("_height", None)

        result = compress_image(image_file, image_type, fmt, animated)

        validated_data.pop("image")
        validated_data["file_name"] = result.file_name
        validated_data.update(
            file_size=result.file_size,
            width=result.width or source_width,
            height=result.height or source_height,
        )
        instance = SiteImage(**validated_data)
        instance.save()
        instance.image.save(result.file_name, ContentFile(result.data), save=True)
        self._save_variants(instance, result, image_type)

        return instance

    def update(self, instance, validated_data):
        image_file = validated_data.get("image")
        if image_file is None:
            validated_data.pop("_fmt", None)
            validated_data.pop("_animated", None)
            return super().update(instance, validated_data)

        fmt = validated_data.pop("_fmt")
        animated = validated_data.pop("_animated")
        source_width = validated_data.pop("_width", None)
        source_height = validated_data.pop("_height", None)
        image_type = validated_data.get("image_type", instance.image_type)
        result = compress_image(image_file, image_type, fmt, animated)

        validated_data.pop("image")
        validated_data["file_name"] = result.file_name
        validated_data.update(
            file_size=result.file_size,
            width=result.width or source_width,
            height=result.height or source_height,
        )
        updated = super().update(instance, validated_data)
        updated.image.save(result.file_name, ContentFile(result.data), save=True)
        self._save_variants(updated, result, image_type)
        return updated

    def _save_variants(self, instance, result, image_type):
        instance.variants.all().delete()
        variants = []
        for variant_data in generate_variants(result, image_type):
            variant = ImageVariant(
                image_upload=instance,
                variant_type=variant_data["variant_type"],
                width=variant_data["width"],
                height=variant_data["height"],
                format=variant_data["format"],
                file_size=variant_data["file_size"],
            )
            variant.image.save(
                variant_data["filename"],
                ContentFile(variant_data["data"]),
                save=False,
            )
            variants.append(variant)

        if variants:
            ImageVariant.objects.bulk_create(variants)

    def get_image_path(self, obj):
        return obj.image.url if obj.image else None


    def get_file_size(self, obj):
        if obj.file_size is None:
            return None
        return f"{round(obj.file_size / 1024, 1)} KB"



class SiteSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ["id", "name", "status", "url"]


class SitePublishVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SitePublishVersion
        fields = [
            "id",
            "site",
            "version_number",
            "header_hash",
            "footer_hash",
            "page_hashes",
            "asset_hashes",
            "published_by",
            "created_at",
        ]
        read_only_fields = fields
