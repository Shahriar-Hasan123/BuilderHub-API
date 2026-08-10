import io
import os
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from apps.core.exceptions import UnsupportedImageFormatError
from apps.core.services.image_optimizer import ImageOptimizer


def _random_png_bytes(width=900, height=900, mode="RGBA"):
    """Genuinely large (>500KB), high-entropy PNG — random pixel data
    defeats PNG's compression, guaranteeing it exceeds the threshold."""
    raw = os.urandom(width * height * len(mode))
    image = Image.frombytes(mode, (width, height), raw)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _solid_png_bytes(size=(10, 10), mode="RGB", color=(255, 0, 0)):
    image = Image.new(mode, size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _solid_gif_bytes(size=(10, 10), color=(255, 0, 0)):
    image = Image.new("RGB", size, color)
    buffer = io.BytesIO()
    image.save(buffer, format="GIF")
    return buffer.getvalue()


class ImageOptimizerCompressTests(TestCase):
    def setUp(self):
        self.optimizer = ImageOptimizer()

    def test_small_png_returns_original_when_jpeg_is_larger(self):
        content = _solid_png_bytes()
        file = SimpleUploadedFile("small.png", content, content_type="image/png")
        result_bytes, name = self.optimizer.compress(file)
        self.assertEqual(result_bytes, content)
        self.assertEqual(name, "small.png")

    def test_svg_skipped_regardless_of_size(self):
        content = os.urandom(510 * 1024)
        file = SimpleUploadedFile("large.svg", content, content_type="image/svg+xml")
        result_bytes, name = self.optimizer.compress(file)
        self.assertEqual(result_bytes, content)

    def test_gif_skipped(self):
        content = _solid_gif_bytes()
        file = SimpleUploadedFile("large.gif", content, content_type="image/gif")
        result_bytes, name = self.optimizer.compress(file)
        self.assertEqual(result_bytes, content)

    def test_unsupported_extension_raises(self):
        file = SimpleUploadedFile(
            "file.txt", b"not an image", content_type="text/plain"
        )
        with self.assertRaises(UnsupportedImageFormatError):
            self.optimizer.compress(file)

    def test_empty_file_raises(self):
        file = SimpleUploadedFile("empty.png", b"", content_type="image/png")
        with self.assertRaises(ValueError):
            self.optimizer.compress(file)

    def test_opaque_large_png_converts_to_jpeg(self):
        content = _random_png_bytes(mode="RGB")
        file = SimpleUploadedFile("photo.png", content, content_type="image/png")
        result_bytes, name = self.optimizer.compress(file)
        self.assertTrue(name.endswith(".jpg"))
        self.assertEqual(Image.open(io.BytesIO(result_bytes)).format, "JPEG")

    def test_transparent_large_png_stays_png(self):
        content = _random_png_bytes(mode="RGBA")
        file = SimpleUploadedFile("logo.png", content, content_type="image/png")
        result_bytes, name = self.optimizer.compress(file)
        self.assertTrue(name.endswith(".png"))
        self.assertEqual(Image.open(io.BytesIO(result_bytes)).format, "PNG")

    def test_uses_detected_format_for_output_filename(self):
        content = _solid_png_bytes(size=(600, 600))
        file = SimpleUploadedFile("wrong.jpg", content, content_type="image/jpeg")
        result_bytes, name = self.optimizer.compress(file)
        self.assertTrue(name.endswith(".png"))
        self.assertEqual(Image.open(io.BytesIO(result_bytes)).format, "PNG")

    def test_rejects_image_over_pixel_limit(self):
        content = _solid_png_bytes(size=(20, 20))
        file = SimpleUploadedFile("large.png", content, content_type="image/png")
        with patch("apps.core.services.image_optimizer.MAX_IMAGE_PIXELS", 100):
            with self.assertRaises(UnsupportedImageFormatError):
                self.optimizer.compress(file)


class ImageOptimizerTransparencyDetectionTests(TestCase):
    def setUp(self):
        self.optimizer = ImageOptimizer()

    def test_fully_opaque_rgba_is_not_transparent(self):
        image = Image.new("RGBA", (10, 10), (255, 0, 0, 255))
        self.assertFalse(self.optimizer._has_transparency(image))

    def test_rgba_with_partial_alpha_is_transparent(self):
        image = Image.new("RGBA", (10, 10), (255, 0, 0, 100))
        self.assertTrue(self.optimizer._has_transparency(image))

    def test_rgb_image_is_not_transparent(self):
        image = Image.new("RGB", (10, 10), (255, 0, 0))
        self.assertFalse(self.optimizer._has_transparency(image))


class ImageOptimizerQuantizationTests(TestCase):
    def setUp(self):
        self.optimizer = ImageOptimizer()

    def test_low_color_image_gets_quantized(self):
        image = Image.new("RGBA", (300, 300), (255, 0, 0, 255))  # single color
        result_bytes, _ = self.optimizer._compress_transparent_png(
            image, "logo.png", None
        )
        result = Image.open(io.BytesIO(result_bytes))
        self.assertEqual(result.mode, "P")

    def test_low_color_image_falls_back_to_webp_when_quantized_exceeds_target(self):
        image = Image.new("RGBA", (300, 300), (255, 0, 0, 100))
        with patch.object(
            self.optimizer,
            "_compress_with_ladder",
            return_value=(b"webp-bytes", "logo.webp"),
        ) as compress_with_ladder:
            result_bytes, name = self.optimizer._compress_transparent_png(
                image, "logo.png", 1
            )

        self.assertEqual(result_bytes, b"webp-bytes")
        self.assertEqual(name, "logo.webp")
        compress_with_ladder.assert_called_once()

    def test_high_color_image_skips_quantization(self):
        # gradient -> thousands of unique colors
        image = Image.new("RGBA", (300, 300))
        pixels = image.load()
        for x in range(300):
            for y in range(300):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256, 255)
        result_bytes, _ = self.optimizer._compress_transparent_png(
            image, "logo.png", None
        )
        result = Image.open(io.BytesIO(result_bytes))
        self.assertEqual(result.mode, "RGBA")  # unchanged, not quantized

    def test_oversized_image_gets_resized(self):
        image = Image.new("RGBA", (2000, 100), (0, 255, 0, 255))
        result_bytes, _ = self.optimizer._compress_transparent_png(
            image, "logo.png", None
        )
        result = Image.open(io.BytesIO(result_bytes))
        self.assertLessEqual(max(result.size), 1500)
