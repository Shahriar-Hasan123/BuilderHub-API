import io
import os

from PIL import Image, ImageOps

from apps.core.exceptions import UnsupportedImageFormatError

PNG_RESIZE_MAX_DIMENSION = 1500
PNG_QUANTIZE_COLOR_LIMIT = 256

MAX_IMAGE_PIXELS = 40_000_000  # ~40 megapixels

QUALITY_STEPS = [75, 60, 45, 35]  # descending retry ladder for lossy formats
RESIZE_RETRY_FACTOR = 0.75  # last-resort downscale if quality alone can't hit target
MAX_RESIZE_RETRIES = 2

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg", ".gif"}
PIL_FORMAT_EXTENSIONS = {
    "PNG": ".png",
    "JPEG": ".jpg",
    "WEBP": ".webp",
    "AVIF": ".avif",
    "GIF": ".gif",
}


class ImageOptimizer:
    """Optimize uploaded images while preserving important visual behavior.

    SVG, GIF, and animated images are returned unchanged. Opaque PNGs may be
    converted to JPEG, transparent PNGs stay lossless unless a target size
    requires WebP fallback, and optimized output is used only when it is
    smaller than the original.
    """

    def compress(self, file, target_kb: int | None = None) -> tuple[bytes, str]:
        """Return optimized image bytes and the filename to save.

        Args:
            file: Uploaded file-like object with ``name``, ``size``, ``read``,
                and ``seek`` attributes.
            target_kb: Optional target size in kilobytes. Lossy formats lower
                quality and then resize when needed to approach this limit.

        Raises:
            ValueError: If the upload is empty.
            UnsupportedImageFormatError: If the extension or image data cannot
                be processed safely.
        """
        if file.size == 0:
            raise ValueError("Cannot compress an empty file")

        ext = os.path.splitext(file.name)[1].lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise UnsupportedImageFormatError(f"Unsupported file extension: {ext}")

        original_bytes = self._as_bytes(file)

        if ext == ".svg":
            return original_bytes, file.name

        target_bytes = target_kb * 1024 if target_kb else None

        file.seek(0)
        try:
            Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
            with Image.open(file) as opened:
                image_format = (opened.format or "").upper()
                if image_format not in PIL_FORMAT_EXTENSIONS:
                    raise UnsupportedImageFormatError(
                        f"Unsupported image format: {image_format or 'unknown'}"
                    )
                if opened.width * opened.height > MAX_IMAGE_PIXELS:
                    raise UnsupportedImageFormatError(
                        "Image is too large to process safely."
                    )
                opened.load()
                is_animated = getattr(opened, "is_animated", False)
                image = ImageOps.exif_transpose(opened.copy())
        except Image.DecompressionBombError as exc:
            raise UnsupportedImageFormatError(
                f"Image is too large to process safely: {exc}"
            )
        except (OSError, ValueError) as exc:
            raise UnsupportedImageFormatError(f"Cannot open image file: {exc}")

        filename = self._with_extension(file.name, PIL_FORMAT_EXTENSIONS[image_format])

        if image_format == "GIF" or is_animated:
            return original_bytes, filename

        if image_format == "PNG":
            candidate = self._compress_png(image, filename, target_bytes)
        else:
            candidate = self._compress_other(
                image, image_format, filename, target_bytes
            )

        return self._keep_smaller(candidate, (original_bytes, filename))

    def _keep_smaller(self, candidate, original):
        return candidate if len(candidate[0]) < len(original[0]) else original

    def _has_transparency(self, image: Image.Image) -> bool:
        if "A" in image.getbands():
            return image.getchannel("A").getextrema()[0] < 255
        if image.mode == "P" and "transparency" in image.info:
            return True
        return False

    def _normalize_for_lossy(self, image: Image.Image) -> Image.Image:
        """Convert uncommon image modes before saving to lossy formats."""
        if image.mode in ("RGB", "RGBA"):
            return image
        return image.convert("RGBA" if self._has_transparency(image) else "RGB")

    def _compress_with_ladder(
        self, image, format, filename, target_bytes, **fixed_kwargs
    ):
        """Try lower quality levels, then bounded resizing, for lossy output."""
        image = self._normalize_for_lossy(image)
        result = None
        for _ in range(MAX_RESIZE_RETRIES + 1):
            for quality in QUALITY_STEPS:
                result = self._save(
                    image, format, filename, quality=quality, **fixed_kwargs
                )
                if target_bytes is None or len(result[0]) <= target_bytes:
                    return result
            if target_bytes is None:
                break
            new_size = (
                max(1, int(image.width * RESIZE_RETRY_FACTOR)),
                max(1, int(image.height * RESIZE_RETRY_FACTOR)),
            )
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        return result

    def _compress_png(self, image: Image.Image, filename: str, target_bytes):
        if self._has_transparency(image):
            return self._compress_transparent_png(image, filename, target_bytes)

        new_name = filename.rsplit(".", 1)[0] + ".jpg"
        return self._compress_with_ladder(
            image.convert("RGB"),
            "JPEG",
            new_name,
            target_bytes,
            optimize=True,
            progressive=True,
            subsampling=2,
        )

    def _compress_transparent_png(
        self, image: Image.Image, filename: str, target_bytes
    ):
        if max(image.size) > PNG_RESIZE_MAX_DIMENSION:
            image = image.copy()
            image.thumbnail(
                (PNG_RESIZE_MAX_DIMENSION, PNG_RESIZE_MAX_DIMENSION),
                Image.Resampling.LANCZOS,
            )

        rgba_image = image.convert("RGBA")
        colors = rgba_image.getcolors(maxcolors=PNG_QUANTIZE_COLOR_LIMIT)

        if colors is not None:
            quantized = rgba_image.quantize(
                colors=PNG_QUANTIZE_COLOR_LIMIT,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.NONE,
            )
            quantized_result = self._save(
                quantized, "PNG", filename, optimize=True, compress_level=9
            )
            if target_bytes is None or len(quantized_result[0]) <= target_bytes:
                return quantized_result

        lossless = self._save(
            rgba_image, "PNG", filename, optimize=True, compress_level=9
        )
        if target_bytes is None or len(lossless[0]) <= target_bytes:
            return lossless

        webp_name = filename.rsplit(".", 1)[0] + ".webp"
        return self._compress_with_ladder(
            rgba_image, "WEBP", webp_name, target_bytes, method=6
        )

    def _compress_other(
        self, image: Image.Image, image_format: str, filename: str, target_bytes
    ):
        if image_format == "JPEG":
            return self._compress_with_ladder(
                image.convert("RGB"),
                "JPEG",
                filename,
                target_bytes,
                optimize=True,
                progressive=True,
                subsampling=2,
            )
        if image_format == "WEBP":
            return self._compress_with_ladder(
                image, "WEBP", filename, target_bytes, method=6
            )
        if image_format == "AVIF":
            return self._compress_with_ladder(
                image, "AVIF", filename, target_bytes, speed=8
            )
        raise UnsupportedImageFormatError(f"No compression handler for: {image_format}")

    def _save(self, image: Image.Image, format: str, filename: str, **kwargs):
        buffer = io.BytesIO()
        image.save(buffer, format=format, **kwargs)
        return buffer.getvalue(), filename

    def _as_bytes(self, file) -> bytes:
        file.seek(0)
        return file.read()

    def _with_extension(self, filename: str, extension: str) -> str:
        return filename.rsplit(".", 1)[0] + extension
