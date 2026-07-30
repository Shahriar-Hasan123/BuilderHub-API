import io
import os

from PIL import Image

from apps.core.exceptions import UnsupportedImageFormatError

COMPRESSION_SKIP_THRESHOLD_KB = 500
PNG_RESIZE_MAX_DIMENSION = 1500
PNG_QUANTIZE_SAMPLE_SIZE = (256, 256)
PNG_QUANTIZE_COLOR_LIMIT = 256

SKIP_COMPRESSION_EXTENSIONS = {".svg", ".gif"}
SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg", ".gif"}


class ImageOptimizer:
    """Upload-time image optimization: skips small/already-efficient files
    and vector/animated formats, converts opaque PNGs to JPEG, keeps
    transparent PNGs as PNG"""

    def compress(self, file):
        if file.size == 0:
            raise ValueError("Cannot compress an empty file")

        ext = os.path.splitext(file.name)[1].lower()

        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedImageFormatError(f"Unsupported file extension: {ext}")

        if (
            file.size <= COMPRESSION_SKIP_THRESHOLD_KB * 1024
            or ext in SKIP_COMPRESSION_EXTENSIONS
        ):
            return self._as_bytes(file), file.name

        file.seek(0)
        try:
            with Image.open(file) as image:
                image.load()
                image = image.copy()
        except (OSError, ValueError) as exc:
            raise UnsupportedImageFormatError(f"Cannot open image file: {exc}")

        if ext == ".png":
            return self._compress_png(image, file.name)

        return self._compress_other(image, ext, file.name)

    def _has_transparency(self, image: Image.Image) -> bool:
        if "A" in image.getbands():
            return image.getchannel("A").getextrema()[0] < 255

        if image.mode == "P" and "transparency" in image.info:
            return True

        return False

    def _compress_png(self, image: Image.Image, filename: str):
        if self._has_transparency(image):
            optimized = self._optimize_transparent_png(image)
            return self._save(
                optimized, "PNG", filename, optimize=True, compress_level=9
            )

        rgb_image = image.convert("RGB")
        new_name = filename.rsplit(".", 1)[0] + ".jpg"
        return self._save(
            rgb_image,
            "JPEG",
            new_name,
            quality=75,
            optimize=True,
            progressive=True,
            subsampling=2,
        )

    def _optimize_transparent_png(self, image: Image.Image) -> Image.Image:

        if max(image.size) > PNG_RESIZE_MAX_DIMENSION:
            image = image.copy()
            image.thumbnail(
                (PNG_RESIZE_MAX_DIMENSION, PNG_RESIZE_MAX_DIMENSION),
                Image.Resampling.LANCZOS,
            )

        sample = image.copy()
        sample.thumbnail(PNG_QUANTIZE_SAMPLE_SIZE)

        colors = sample.convert("RGBA").getcolors(maxcolors=100000)

        # Photo-like transparent PNG
        if colors is None or len(colors) > PNG_QUANTIZE_COLOR_LIMIT:
            return image

        if "A" in image.getbands():
            return image.quantize(
                colors=PNG_QUANTIZE_COLOR_LIMIT,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.NONE,
            )

        if image.mode == "P" and "transparency" in image.info:
            return image.convert("RGBA").quantize(
                colors=PNG_QUANTIZE_COLOR_LIMIT,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.NONE,
            )

        return image.convert("RGB").quantize(
            colors=PNG_QUANTIZE_COLOR_LIMIT,
            method=Image.Quantize.MEDIANCUT,
            dither=Image.Dither.NONE,
        )

    def _compress_other(self, image: Image.Image, ext: str, filename: str):
        if ext in (".jpg", ".jpeg"):
            return self._save(
                image.convert("RGB"),
                "JPEG",
                filename,
                quality=75,
                optimize=True,
                progressive=True,
                subsampling=2,
            )
        if ext == ".webp":
            return self._save(
                image, "WEBP", filename, quality=75, method=6, lossless=False
            )
        if ext == ".avif":
            return self._save(image, "AVIF", filename, quality=60, speed=8)

        raise UnsupportedImageFormatError(f"No compression handler for: {ext}")

    def _save(self, image: Image.Image, format: str, filename: str, **kwargs):
        buffer = io.BytesIO()
        image.save(buffer, format=format, **kwargs)
        return buffer.getvalue(), filename

    def _as_bytes(self, file) -> bytes:
        file.seek(0)
        return file.read()
