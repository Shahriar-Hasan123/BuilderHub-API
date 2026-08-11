import io
import os

from PIL import Image, ImageOps

from apps.core.exceptions import UnsupportedImageFormatError

PNG_RESIZE_MAX_DIMENSION = 1500
PNG_QUANTIZE_COLOR_LIMIT = 256

MAX_IMAGE_PIXELS = 40_000_000  # ~40 megapixels

Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS

QUALITY_STEPS = [75, 60, 45, 35]  # descending retry ladder for lossy formats
RESIZE_RETRY_FACTOR = 0.75  # last-resort downscale if quality alone can't hit target
MAX_RESIZE_RETRIES = 2
ALREADY_LOSSY_FORMATS = {"JPEG"}

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

    SVG, GIF, and animated images are returned unchanged. By default, raster
    images only use non-resizing, lossless optimization attempts. Lossy
    compression and resizing must be explicitly enabled by the caller, and
    optimized output is used only when it is smaller than the original.
    """

    def compress(
        self,
        file,
        target_kb: int | None = None,
        *,
        allow_lossy: bool = False,
        allow_resize: bool = False,
        max_dimension: int = PNG_RESIZE_MAX_DIMENSION,
    ) -> tuple[bytes, str]:
        """Return optimized image bytes and the filename to save.

        Args:
            file: Uploaded file-like object with ``name``, ``size``, ``read``,
                and ``seek`` attributes.
            target_kb: Optional target size in kilobytes. This method is
                best-effort; callers that need a hard limit should re-check the
                returned size.
            allow_lossy: Whether JPEG quality reduction may be used.
            allow_resize: Whether lossy retry steps may downscale dimensions.
            max_dimension: Longest side used when resizing is allowed.

        Raises:
            ValueError: If the upload is empty.
            UnsupportedImageFormatError: If the extension or image data cannot
                be processed safely.

        Note:
            SVG safety is assumed to have been validated upstream. SVG uploads
            are passed through unchanged based on extension.
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
                icc_profile = opened.info.get("icc_profile")
                image = ImageOps.exif_transpose(opened.copy())

        except Image.DecompressionBombError as exc:
            raise UnsupportedImageFormatError(
                f"Image is too large to process safely: {exc}"
            ) from exc
        except (OSError, ValueError) as exc:
            raise UnsupportedImageFormatError(f"Cannot open image file: {exc}") from exc

        base_name = os.path.splitext(file.name)[0]

        if image_format == "GIF" or is_animated:
            return original_bytes, base_name + PIL_FORMAT_EXTENSIONS[image_format]

        candidate = self._compress_image(
            image=image,
            image_format=image_format,
            base_name=base_name,
            target_bytes=target_bytes,
            icc_profile=icc_profile,
            allow_lossy=allow_lossy,
            allow_resize=allow_resize,
            max_dimension=max_dimension,
        )

        return self._keep_smaller(candidate, (original_bytes, file.name))

    def _keep_smaller(self, candidate, original):
        if candidate is None:
            return original
        return candidate if len(candidate[0]) < len(original[0]) else original

    def _has_transparency(self, image: Image.Image) -> bool:
        if "A" in image.getbands():
            return image.getchannel("A").getextrema()[0] < 255
        if image.mode == "P" and "transparency" in image.info:
            return True
        return False

    def _compress_image(
        self,
        image: Image.Image,
        image_format: str,
        base_name: str,
        target_bytes: int | None,
        icc_profile: bytes | None,
        allow_lossy: bool,
        allow_resize: bool,
        max_dimension: int,
    ):
        has_alpha = self._has_transparency(image)
        source_image = image.convert("RGBA" if has_alpha else "RGB")
        icc_kwargs = {"icc_profile": icc_profile} if icc_profile else {}

        def hits_target(result):
            return target_bytes is None or len(result[0]) <= target_bytes

        best_result = None

        colors = source_image.getcolors(maxcolors=PNG_QUANTIZE_COLOR_LIMIT)
        if colors is not None:
            quantized = source_image.quantize(
                colors=PNG_QUANTIZE_COLOR_LIMIT,
                method=Image.Quantize.FASTOCTREE,
                dither=Image.Dither.NONE,
            )
            quantized_result = self._save(
                quantized,
                "PNG",
                f"{base_name}.png",
                optimize=True,
                compress_level=9,
            )
            if hits_target(quantized_result):
                return quantized_result
            best_result = quantized_result

        if image_format in ALREADY_LOSSY_FORMATS and colors is None:
            return self._maybe_lossy_fallback(
                source_image=source_image,
                base_name=base_name,
                target_bytes=target_bytes,
                has_alpha=has_alpha,
                best_result=best_result,
                allow_lossy=allow_lossy,
                allow_resize=allow_resize,
                max_dimension=max_dimension,
                icc_kwargs=icc_kwargs,
            )

        lossless_png = self._save(
            source_image,
            "PNG",
            f"{base_name}.png",
            optimize=True,
            compress_level=9,
            **icc_kwargs,
        )
        if best_result is None or len(lossless_png[0]) < len(best_result[0]):
            best_result = lossless_png
        if hits_target(lossless_png):
            return lossless_png

        lossless_webp = self._save(
            source_image,
            "WEBP",
            f"{base_name}.webp",
            lossless=True,
            method=6,
            **icc_kwargs,
        )
        if len(lossless_webp[0]) < len(best_result[0]):
            best_result = lossless_webp
        if hits_target(lossless_webp):
            return lossless_webp

        return self._maybe_lossy_fallback(
            source_image=source_image,
            base_name=base_name,
            target_bytes=target_bytes,
            has_alpha=has_alpha,
            best_result=best_result,
            allow_lossy=allow_lossy,
            allow_resize=allow_resize,
            max_dimension=max_dimension,
            icc_kwargs=icc_kwargs,
        )

    def _maybe_lossy_fallback(
        self,
        source_image,
        base_name,
        target_bytes,
        has_alpha,
        best_result,
        allow_lossy,
        allow_resize,
        max_dimension,
        icc_kwargs,
    ):
        if not allow_lossy:
            return best_result

        if has_alpha:
            lossy_result = self._compress_with_ladder(
                source_image,
                "WEBP",
                f"{base_name}.webp",
                target_bytes,
                allow_resize=allow_resize,
                max_dimension=max_dimension,
                method=6,
                **icc_kwargs,
            )
        else:
            lossy_result = self._compress_with_ladder(
                source_image,
                "JPEG",
                f"{base_name}.jpg",
                target_bytes,
                allow_resize=allow_resize,
                max_dimension=max_dimension,
                optimize=True,
                progressive=True,
                subsampling=2,
                **icc_kwargs,
            )

        if best_result is None or len(lossy_result[0]) < len(best_result[0]):
            return lossy_result
        return best_result

    def _compress_with_ladder(
        self,
        image,
        format,
        filename,
        target_bytes,
        *,
        allow_resize,
        max_dimension,
        **fixed_kwargs,
    ):
        """Try lower quality levels, then bounded resizing, for lossy output."""
        result = None
        for resize_attempt in range(MAX_RESIZE_RETRIES + 1):
            if allow_resize and max(image.size) > max_dimension:
                image = image.copy()
                image.thumbnail(
                    (max_dimension, max_dimension), Image.Resampling.LANCZOS
                )

            for quality in QUALITY_STEPS:
                result = self._save(
                    image, format, filename, quality=quality, **fixed_kwargs
                )
                if target_bytes is None or len(result[0]) <= target_bytes:
                    return result

            if not allow_resize or target_bytes is None:
                break

            if resize_attempt < MAX_RESIZE_RETRIES:
                new_size = (
                    max(1, int(image.width * RESIZE_RETRY_FACTOR)),
                    max(1, int(image.height * RESIZE_RETRY_FACTOR)),
                )
                image = image.resize(new_size, Image.Resampling.LANCZOS)
        return result

    def _save(self, image: Image.Image, format: str, filename: str, **kwargs):
        buffer = io.BytesIO()
        image.save(buffer, format=format, **kwargs)
        return buffer.getvalue(), filename

    def _as_bytes(self, file) -> bytes:
        file.seek(0)
        return file.read()
