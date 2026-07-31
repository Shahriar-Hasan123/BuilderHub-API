import os

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible
from PIL import Image, UnidentifiedImageError


@deconstructible
class ImageValidator:
    def __init__(
        self,
        min_width=None,
        min_height=None,
        max_width=None,
        max_height=None,
        allowed_formats=("PNG", "JPEG", "WEBP", "GIF", "AVIF", "SVG"),
    ):
        self.min_width = min_width
        self.min_height = min_height
        self.max_width = max_width
        self.max_height = max_height
        self.allowed_formats = tuple(fmt.upper() for fmt in allowed_formats)

    def __call__(self, file):
        ext = os.path.splitext(file.name)[1].lower()
        if ext == ".svg":
            self._validate_svg(file)
            return

        self._validate_raster(file)

    def _validate_svg(self, file):
        if "SVG" not in self.allowed_formats:
            raise ValidationError("SVG format is not allowed for this field.")
        file.seek(0)
        header = file.read(1024).decode("utf-8", errors="ignore")
        file.seek(0)
        if "<svg" not in header.lower():
            raise ValidationError("File is not a valid SVG.")

    def _validate_raster(self, file):
        file.seek(0)
        try:
            with Image.open(file) as image:
                image_format = image.format
                width, height = image.size
                image.verify()
        except (UnidentifiedImageError, OSError):
            raise ValidationError("File is not a valid image.")
        finally:
            file.seek(0)

        if image_format not in self.allowed_formats:
            raise ValidationError(
                f"Unsupported image format '{image_format}'. "
                f"Allowed: {', '.join(self.allowed_formats)}."
            )

        if self.min_width and width < self.min_width:
            raise ValidationError(
                f"Image width must be at least {self.min_width}px (got {width}px)."
            )
        if self.min_height and height < self.min_height:
            raise ValidationError(
                f"Image height must be at least {self.min_height}px (got {height}px)."
            )
        if self.max_width and width > self.max_width:
            raise ValidationError(
                f"Image width must not exceed {self.max_width}px (got {width}px)."
            )
        if self.max_height and height > self.max_height:
            raise ValidationError(
                f"Image height must not exceed {self.max_height}px (got {height}px)."
            )

    def __eq__(self, other):
        return (
            isinstance(other, ImageValidator)
            and self.min_width == other.min_width
            and self.min_height == other.min_height
            and self.max_width == other.max_width
            and self.max_height == other.max_height
            and self.allowed_formats == other.allowed_formats
        )


validate_favicon_image = ImageValidator(
    min_width=16,
    min_height=16,
    max_width=1000,
    max_height=1000,
)

validate_logo_image = ImageValidator(
    min_width=100,
    min_height=100,
    max_width=2000,
    max_height=2000,
)

validate_thumbnail_image = ImageValidator(
    min_width=150,
    min_height=150,
    max_width=1500,
    max_height=1500,
)

validate_hero_image = ImageValidator(
    min_width=500,
    min_height=300,
    max_width=3840,
    max_height=2160,
)

validate_content_image = ImageValidator(
    min_width=20,
    min_height=20,
    max_width=6000,
    max_height=6000,
)

html_file_validator = FileExtensionValidator(allowed_extensions=["html"])
css_file_validator = FileExtensionValidator(allowed_extensions=["css"])

MAX_FILE_SIZE_BYTES = 500 * 1024


def validate_file_size(file):
    if file.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"File size must not exceed {MAX_FILE_SIZE_BYTES / 1024:.0f} KB. "
            f"Uploaded file is {file.size / 1024:.1f} KB."
        )
