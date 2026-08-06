from django.core.files.base import ContentFile
from rest_framework import serializers

from apps.core.services.image_optimizer import ImageOptimizer


class ImageFieldProcessor:
    """Compresses configured image fields on a serializer's validated_data and
    re-checks each field's size against its max_kb after compression."""

    def __init__(self):
        self.optimizer = ImageOptimizer()

    def process(self, fields, validated_data):
        """fields: {field_name: max_kb} mapping, as defined per-serializer."""
        for field_name, max_kb in fields.items():
            uploaded_file = validated_data.get(field_name)
            if not uploaded_file:
                continue

            try:
                content_bytes, filename = self.optimizer.compress(uploaded_file)
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
