from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
import xml.etree.ElementTree as ET
from PIL import Image, UnidentifiedImageError
from apps.core.constants import DIMENSION_CONSTRAINTS, MAX_UPLOAD_BYTES, MAX_IMAGE_PIXELS


html_file_validator = FileExtensionValidator(allowed_extensions=["html"])
css_file_validator = FileExtensionValidator(allowed_extensions=["css"])

MAX_FILE_SIZE_BYTES = 500 * 1024


def validate_file_size(file):
    if file.size > MAX_FILE_SIZE_BYTES:
        raise ValidationError(
            f"File size must not exceed {MAX_FILE_SIZE_BYTES / 1024:.0f} KB. "
            f"Uploaded file is {file.size / 1024:.1f} KB."
        )


def validate_upload_size(file):
    if file.size == 0:
        raise ValidationError("Uploaded file is empty.")
    if file.size > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"File exceeds max upload size of {MAX_UPLOAD_BYTES} bytes."
        )


def _looks_like_svg(head: bytes) -> bool:
    try:
        # Real content validation, not extension trust: parse as XML and check
        # the root tag is actually <svg>, not just substring-matching bytes.
        root = ET.fromstring(head)
        return root.tag.endswith("svg")
    except ET.ParseError:
        return False


def detect_format(file) -> str:
    """Sniff real format from content. Raises on anything unrecognized."""
    
    file.seek(0)
    head = file.read(4096)
    file.seek(0)

    if head.strip().startswith(b"<") and _looks_like_svg(head):
        return "SVG"

    try:
        with Image.open(file) as img:
            img.verify()  # raises if the file is truncated/corrupt
        file.seek(0)
        with Image.open(file) as img:
            fmt = img.format
        file.seek(0)
        return fmt
    except (UnidentifiedImageError, OSError, SyntaxError):
        raise ValidationError("File is not a valid, recognized image.")


def is_animated(file, fmt) -> bool:
    """Animated GIF/WEBP/PNG must be returned unchanged — frame-flattening
    would silently destroy the animation, so this is checked explicitly."""
    
    if fmt not in ("GIF", "WEBP", "PNG"):
        return False
    file.seek(0)
    with Image.open(file) as img:
        result = getattr(img, "is_animated", False)
    file.seek(0)
    return result


def get_dimensions(file, fmt):
    if fmt == "SVG":
        return None, None
    file.seek(0)
    with Image.open(file) as img:
        w, h = img.size
        if w * h > MAX_IMAGE_PIXELS:
            raise ValidationError(
                f"Image has {w*h} pixels, exceeds safety limit of {MAX_IMAGE_PIXELS}."
            )
    file.seek(0)
    return w, h


def validate_image_type(image_type):
    try:
        return DIMENSION_CONSTRAINTS[image_type]
    except KeyError as exc:
        raise ValidationError(f"Unsupported image type: {image_type!r}.") from exc


def validate_min_dimensions(width, height, image_type):
    if width is None:
        return
    c = validate_image_type(image_type)
    if width < c["min_w"] or height < c["min_h"]:
        raise ValidationError(
            f"Image too small: {width}x{height}px, minimum is "
            f"{c['min_w']}x{c['min_h']}px for '{image_type}'. Upscaling would degrade quality."
        )


def _validate_model_image(file, image_type=None):
    validate_upload_size(file)
    if image_type:
        validate_image_type(image_type)
    fmt = detect_format(file)
    width, height = get_dimensions(file, fmt)
    if image_type:
        validate_min_dimensions(width, height, image_type)



def validate_regular_image(file):
    _validate_model_image(file, "regular")


def validate_favicon_image(file):
    _validate_model_image(file, "favicon")


def validate_logo_image(file):
    _validate_model_image(file, "logo")


def validate_thumbnail_image(file):
    _validate_model_image(file, "thumbnail")


def validate_hero_image(file):
    _validate_model_image(file, "hero")

