from django.core.files.base import ContentFile
from rest_framework import serializers

from apps.core.exceptions import ResourceLockedError, SiteLockedAPIException
from apps.core.services.image_optimizer import ImageOptimizer
from apps.core.services.resource_lock import SiteLockService


class SiteLockMixin:
    def enforce_site_lock(self, request, site):
        try:
            SiteLockService().acquire(site.id, request.user)
        except ResourceLockedError as exc:
            raise SiteLockedAPIException(
                detail=f"This site is currently being edited by {exc.locked_by}. Please try again later."
            )


class ImageOptimizationMixin:
    """After DRF's normal field validation passes, this compresses each configured image
    field and re-checks the compressed size"""

    optimized_image_fields = {}  # {field_name: max_kb}

    def _optimize_images(self, validated_data):
        optimizer = ImageOptimizer()
        for field_name, max_kb in self.optimized_image_fields.items():
            uploaded_file = validated_data.get(field_name)
            if not uploaded_file:
                continue

            try:
                content_bytes, filename = optimizer.compress(uploaded_file)
            except Exception as exc:
                raise serializers.ValidationError(
                    {field_name: f"Could not process image: {exc}"}
                )

            if len(content_bytes) > max_kb * 1024:
                raise serializers.ValidationError(
                    {
                        field_name: (
                            f"Even after compression, this image exceeds {max_kb} KB "
                            f"(got {len(content_bytes) / 1024:.1f} KB)."
                        )
                    }
                )

            validated_data[field_name] = ContentFile(content_bytes, name=filename)
        return validated_data

    def create(self, validated_data):
        validated_data = self._optimize_images(validated_data)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data = self._optimize_images(validated_data)
        return super().update(instance, validated_data)
