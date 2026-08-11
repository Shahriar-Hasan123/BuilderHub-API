import io
import os
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
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


class ImageOptimizerCompressTests(SimpleTestCase):
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

    def test_opaque_large_png_converts_to_jpeg_when_lossy_is_allowed_for_target(self):
        content = _random_png_bytes(mode="RGB")
        file = SimpleUploadedFile("photo.png", content, content_type="image/png")
        result_bytes, name = self.optimizer.compress(
            file, target_kb=150, allow_lossy=True
        )
        self.assertTrue(name.endswith(".jpg"))
        self.assertEqual(Image.open(io.BytesIO(result_bytes)).format, "JPEG")

    def test_transparent_large_png_does_not_convert_to_jpeg(self):
        content = _random_png_bytes(mode="RGBA")
        file = SimpleUploadedFile("logo.png", content, content_type="image/png")
        result_bytes, name = self.optimizer.compress(file)
        self.assertFalse(name.endswith(".jpg"))
        self.assertIn(Image.open(io.BytesIO(result_bytes)).format, {"PNG", "WEBP"})

    def test_jpeg_is_not_recompressed_by_default(self):
        image = Image.new("RGB", (300, 300), (120, 80, 40))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=85)
        content = buffer.getvalue()
        file = SimpleUploadedFile("photo.jpg", content, content_type="image/jpeg")

        result_bytes, name = self.optimizer.compress(file)

        self.assertEqual(result_bytes, content)
        self.assertEqual(name, "photo.jpg")

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


class ImageOptimizerTransparencyDetectionTests(SimpleTestCase):
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


class ImageOptimizerQuantizationTests(SimpleTestCase):
    def setUp(self):
        self.optimizer = ImageOptimizer()

    def test_low_color_opaque_png_prefers_lossless_png_when_target_is_not_set(self):
        image = Image.new("RGB", (20, 20), (255, 0, 0))
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        file = SimpleUploadedFile(
            "icon.png", buffer.getvalue(), content_type="image/png"
        )

        result_bytes, name = self.optimizer.compress(file)
        result_image = Image.open(io.BytesIO(result_bytes))

        self.assertEqual(name, "icon.png")
        self.assertEqual(result_image.format, "PNG")

    def test_low_color_image_gets_palette_optimized(self):
        image = Image.new("RGBA", (300, 300), (255, 0, 0, 255))  # single color
        result_bytes, _ = self.optimizer._compress_image(
            image=image,
            image_format="PNG",
            base_name="logo",
            target_bytes=None,
            icc_profile=None,
            allow_lossy=False,
            allow_resize=False,
            max_dimension=1500,
        )
        result = Image.open(io.BytesIO(result_bytes))
        self.assertEqual(result.mode, "P")

    def test_lossy_fallback_is_used_only_when_allowed(self):
        image = Image.new("RGBA", (300, 300), (255, 0, 0, 100))
        with patch.object(
            self.optimizer,
            "_compress_with_ladder",
            return_value=(b"webp-bytes", "logo.webp"),
        ) as compress_with_ladder:
            result_bytes, name = self.optimizer._compress_image(
                image=image,
                image_format="PNG",
                base_name="logo",
                target_bytes=1,
                icc_profile=None,
                allow_lossy=True,
                allow_resize=False,
                max_dimension=1500,
            )

        self.assertEqual(result_bytes, b"webp-bytes")
        self.assertEqual(name, "logo.webp")
        compress_with_ladder.assert_called_once()

    def test_lossy_webp_fallback_preserves_icc_profile_for_alpha_images(self):
        image = Image.new("RGBA", (300, 300), (255, 0, 0, 100))
        icc_profile = b"icc-profile-bytes"

        with patch.object(
            self.optimizer,
            "_compress_with_ladder",
            return_value=(b"webp-bytes", "logo.webp"),
        ) as compress_with_ladder:
            self.optimizer._compress_image(
                image=image,
                image_format="PNG",
                base_name="logo",
                target_bytes=1,
                icc_profile=icc_profile,
                allow_lossy=True,
                allow_resize=False,
                max_dimension=1500,
            )

        _, kwargs = compress_with_ladder.call_args
        self.assertIn("icc_profile", kwargs)
        self.assertEqual(kwargs["icc_profile"], icc_profile)

    def test_high_color_image_skips_quantization(self):
        # gradient -> thousands of unique colors
        image = Image.new("RGBA", (300, 300))
        pixels = image.load()
        for x in range(300):
            for y in range(300):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256, 255)
        result_bytes, _ = self.optimizer._compress_image(
            image=image,
            image_format="PNG",
            base_name="logo",
            target_bytes=None,
            icc_profile=None,
            allow_lossy=False,
            allow_resize=False,
            max_dimension=1500,
        )
        result = Image.open(io.BytesIO(result_bytes))
        self.assertNotEqual(result.mode, "P")  # not quantized

    def test_default_path_does_not_resize(self):
        image = Image.new("RGBA", (2000, 100), (0, 255, 0, 255))
        result_bytes, _ = self.optimizer._compress_image(
            image=image,
            image_format="PNG",
            base_name="logo",
            target_bytes=None,
            icc_profile=None,
            allow_lossy=False,
            allow_resize=False,
            max_dimension=1500,
        )
        result = Image.open(io.BytesIO(result_bytes))
        self.assertEqual(result.size, (2000, 100))

    def test_lossy_resize_is_opt_in(self):
        image = Image.new("RGB", (2000, 1000), (0, 255, 0))
        result_bytes, _ = self.optimizer._compress_with_ladder(
            image,
            "JPEG",
            "photo.jpg",
            target_bytes=1,
            allow_resize=True,
            max_dimension=1500,
            optimize=True,
            progressive=True,
            subsampling=2,
        )
        result = Image.open(io.BytesIO(result_bytes))
        self.assertLess(max(result.size), 1500)

    def test_lossy_source_low_color_keeps_original_for_jpeg_when_lossy_is_not_allowed(self):
        image = Image.new("RGB", (300, 300), (255, 0, 0))
        result = self.optimizer._compress_image(
            image=image,
            image_format="JPEG",
            base_name="logo",
            target_bytes=None,
            icc_profile=None,
            allow_lossy=False,
            allow_resize=False,
            max_dimension=1500,
        )

        self.assertIsNone(result)

    def test_avif_source_attempts_same_format_lossless_candidate(self):
        image = Image.new("RGB", (100, 100), (255, 0, 0))
        with patch.object(self.optimizer, "_save", wraps=self.optimizer._save) as save_mock:
            self.optimizer._compress_image(
                image=image,
                image_format="AVIF",
                base_name="photo",
                target_bytes=None,
                icc_profile=None,
                allow_lossy=False,
                allow_resize=False,
                max_dimension=1500,
            )

        self.assertTrue(
            any(call.args[1] == "AVIF" for call in save_mock.call_args_list),
            "Expected AVIF lossless candidate to be attempted for AVIF source",
        )

    def test_webp_source_attempts_same_format_lossless_candidate(self):
        image = Image.new("RGB", (100, 100), (255, 0, 0))
        with patch.object(self.optimizer, "_save", wraps=self.optimizer._save) as save_mock:
            self.optimizer._compress_image(
                image=image,
                image_format="WEBP",
                base_name="photo",
                target_bytes=None,
                icc_profile=None,
                allow_lossy=False,
                allow_resize=False,
                max_dimension=1500,
            )

        self.assertTrue(
            any(call.args[1] == "WEBP" for call in save_mock.call_args_list),
            "Expected WEBP lossless candidate to be attempted for WEBP source",
        )

    def test_lossy_source_high_color_skips_full_lossless(self):
        image = Image.new("RGB", (300, 300))
        pixels = image.load()
        for x in range(300):
            for y in range(300):
                pixels[x, y] = (x % 256, y % 256, (x + y) % 256)

        with patch.object(
            self.optimizer,
            "_compress_with_ladder",
            return_value=(b"lossy-bytes", "photo.jpg"),
        ):
            with patch.object(
                self.optimizer, "_save", wraps=self.optimizer._save
            ) as save_mock:
                result_bytes, name = self.optimizer._compress_image(
                    image=image,
                    image_format="JPEG",
                    base_name="photo",
                    target_bytes=1,
                    icc_profile=None,
                    allow_lossy=True,
                    allow_resize=False,
                    max_dimension=1500,
                )

        self.assertEqual(name, "photo.jpg")
        self.assertFalse(
            any(call.args[1] in {"PNG", "WEBP"} for call in save_mock.call_args_list),
            "Expected high-color lossy source to skip full lossless PNG/WebP tiers",
        )
