import io

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from PIL import Image

from apps.core.validators import MAX_FILE_SIZE_BYTES, ImageValidator, validate_file_size


def _solid_png_bytes(size=(10, 10), mode="RGB", color=(255, 0, 0)):
    image = Image.new(mode, size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


class ImageValidatorTests(SimpleTestCase):
    def test_accepts_valid_png(self):
        content = _solid_png_bytes()
        file = SimpleUploadedFile("logo.png", content, content_type="image/png")
        validator = ImageValidator(min_width=5, min_height=5)
        validator(file)

    def test_rejects_invalid_image_bytes(self):
        file = SimpleUploadedFile("bad.png", b"not-an-image", content_type="image/png")
        validator = ImageValidator()
        with self.assertRaises(ValidationError):
            validator(file)

    def test_rejects_unsupported_format(self):
        image = Image.new("RGB", (10, 10), (255, 0, 0))
        buffer = io.BytesIO()
        image.save(buffer, format="BMP")
        content = buffer.getvalue()
        file = SimpleUploadedFile("photo.bmp", content, content_type="image/bmp")
        validator = ImageValidator(allowed_formats=("PNG",))
        with self.assertRaises(ValidationError) as ctx:
            validator(file)
        self.assertIn("Unsupported image format", str(ctx.exception))

    def test_rejects_below_minimum_dimensions(self):
        content = _solid_png_bytes(size=(20, 20))
        file = SimpleUploadedFile("small.png", content, content_type="image/png")
        validator = ImageValidator(min_width=50, min_height=50)
        with self.assertRaises(ValidationError) as ctx:
            validator(file)
        self.assertIn("Image width must be at least", str(ctx.exception))

    def test_accepts_valid_svg_when_allowed(self):
        svg_content = b"<svg xmlns='http://www.w3.org/2000/svg'></svg>"
        file = SimpleUploadedFile("icon.svg", svg_content, content_type="image/svg+xml")
        validator = ImageValidator(allowed_formats=("SVG",))
        validator(file)

    def test_rejects_invalid_svg(self):
        svg_content = b"<html></html>"
        file = SimpleUploadedFile("icon.svg", svg_content, content_type="image/svg+xml")
        validator = ImageValidator(allowed_formats=("SVG",))
        with self.assertRaises(ValidationError):
            validator(file)


class FileSizeValidatorTests(SimpleTestCase):
    def test_accepts_under_limit(self):
        file = SimpleUploadedFile("test.txt", b"a" * 100, content_type="text/plain")
        validate_file_size(file)

    def test_rejects_over_limit(self):
        file = SimpleUploadedFile(
            "large.txt", b"a" * (MAX_FILE_SIZE_BYTES + 1), content_type="text/plain"
        )
        with self.assertRaises(ValidationError):
            validate_file_size(file)
