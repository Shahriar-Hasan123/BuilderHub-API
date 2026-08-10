# Image Optimization Report — 2026-08-10

## Task Overview
This feature improves the image upload pipeline by validating images safely, optimizing raster images at upload time, preserving formats that should not be recompressed, and enforcing field-specific size limits before files are saved.

Main files:
- `apps/core/validators.py`
- `apps/core/services/image_optimizer.py`
- `apps/core/utils/image_field_processor.py`
- `apps/core/tests/test_image_optimizer.py`
- `apps/core/tests/test_validators.py`
- `requirements.txt`

## Architecture Summary

The feature is split into three responsibilities:

1. `ImageValidator`
   - Validates image type and dimensions before serializer save.
   - Handles raster images with Pillow.
   - Handles SVGs with safe XML parsing through `defusedxml`.

2. `ImageFieldProcessor`
   - Runs during serializer `create()` and `update()`.
   - Calls the optimizer for configured image fields.
   - Re-checks the final optimized size against each field's max KB limit.
   - Replaces the upload with a Django `ContentFile` before model save.

3. `ImageOptimizer`
   - Compresses raster images.
   - Preserves SVG, GIF, and animated images.
   - Applies adaptive compression for lossy formats.
   - Falls back to the original if optimization would make the file larger.

## High-Level Upload Flow

```text
Client multipart upload
        |
        v
DRF serializer validation
        |
        v
ImageValidator / file validators
        |
        |-- SVG -> safe XML parse, safety checks, dimension checks
        |
        |-- Raster -> Pillow verify, format checks, dimension checks
        |
        v
Serializer create() / update()
        |
        v
ImageFieldProcessor.process(fields, validated_data)
        |
        v
ImageOptimizer.compress(uploaded_file, target_kb=max_kb)
        |
        v
Final size check against max_kb
        |
        |-- too large -> serializer.ValidationError
        |
        |-- valid -> ContentFile assigned back to validated_data
        |
        v
Model save + Django storage
```

## Optimizer Decision Flow

```text
ImageOptimizer.compress(file, target_kb)
        |
        v
Check empty file and supported extension
        |
        v
Read original bytes
        |
        |-- .svg -> return original bytes unchanged
        |
        v
Open raster with Pillow
        |
        v
Detect real image format from Pillow, not filename extension
        |
        v
Reject unsupported decoded formats
        |
        v
Check width * height <= MAX_IMAGE_PIXELS
        |
        v
Load image and apply EXIF transpose
        |
        |-- GIF or animated image -> return original bytes unchanged
        |
        v
Normalize output filename extension from detected format
        |
        |-- PNG
        |     |
        |     |-- detect real transparency
        |     |-- normalize transparent PNGs to RGBA, opaque PNGs to RGB
        |     |-- resize very large PNGs to max 1500px side
        |     |-- count colors on the normalized image
        |     |-- <=256 colors -> quantized PNG
        |     |-- if still above target -> lossless PNG attempt
        |     |
        |     |-- transparent fallback -> lossless WEBP, then lossy WEBP
        |     |
        |     |-- opaque fallback -> adaptive JPEG compression
        |
        |-- JPEG / WEBP / AVIF -> adaptive lossy compression
        |
        v
Compare candidate bytes with original bytes
        |
        |-- candidate smaller -> return candidate
        |
        |-- candidate same/larger -> return original
```

## Adaptive Compression Flow

Lossy formats use the same retry ladder:

```text
quality 75
   |
   |-- if <= target -> return
   v
quality 60
   |
   |-- if <= target -> return
   v
quality 45
   |
   |-- if <= target -> return
   v
quality 35
   |
   |-- if <= target -> return
   v
resize to 75% width/height
   |
   v
repeat quality ladder up to 2 resize retries
```

If no target size is supplied, the optimizer tries normal compression once through the quality ladder and then relies on the "never bigger than original" safety net.

## Key Behaviors

### Never bigger than original
Every compression path returns a candidate result first, then `_keep_smaller()` compares the candidate byte length with the original byte length. The optimized result is only used when it is smaller. This prevents the common issue where recompressing already-efficient images makes them bigger.

### Actual format detection
Raster routing uses Pillow's decoded format, not only the uploaded filename extension. If a PNG is uploaded as `wrong.jpg`, the optimizer still treats it as PNG and normalizes the output filename extension.

### PNG handling
PNG images use a shared lossless-first path before format-specific fallback:
- Low-color PNGs, whether transparent or opaque, can be quantized as PNG.
- PNGs are resized to a maximum 1500px side before lossless attempts.
- Quantized PNGs also check `target_bytes`; they no longer return early when still too large.
- Transparent PNGs preserve alpha and try lossless WEBP before falling back to lossy WEBP.
- Opaque PNGs can fall back to adaptive JPEG compression because transparency does not need to be preserved. This usually gives much smaller files for photo-like PNG uploads.

### Animated image preservation
GIF and animated raster images are returned unchanged. This avoids silently converting an animation into a static first frame.

### EXIF orientation
`ImageOps.exif_transpose()` is applied after load so phone/camera images keep their expected orientation after metadata is dropped during save.

### Decompression-bomb protection
The optimizer checks `opened.width * opened.height` before loading image pixels. Images above `MAX_IMAGE_PIXELS` are rejected safely before expensive memory work.

### WEBP/AVIF mode safety
Palette, CMYK, and other uncommon modes are normalized to RGB or RGBA before saving to lossy formats. This avoids encoder crashes.

## SVG Validation Flow

SVGs are not optimized by Pillow. They are validated and then passed through unchanged.

```text
ImageValidator(file)
        |
        |-- extension == .svg
        |
        v
Read SVG bytes
        |
        v
Parse with defusedxml
        |
        |-- invalid XML / unsafe XML -> ValidationError
        |
        v
Confirm root tag is <svg>
        |
        v
Reject unsafe SVG content
        |
        |-- blocked tags: script, foreignObject, iframe, object, embed
        |-- blocked attributes: onclick/onload/etc.
        |-- blocked values: javascript:, data:text/html
        |
        v
If dimension rules exist:
        |
        |-- use width/height
        |-- otherwise use viewBox
        |-- enforce min/max width and height
```

This keeps SVG support while reducing the risk of malformed or scriptable SVG uploads.

## Field Integration

Configured serializer fields provide their target sizes:

```text
SiteSerializer:
  favicon   -> 50 KB
  logo      -> 50 KB
  thumbnail -> 50 KB

SiteImageSerializer:
  image     -> 150 KB

PageSerializer:
  hero_image -> 300 KB
```

The field processor passes each size as `target_kb` to `ImageOptimizer.compress()`. After optimization, the field processor checks the final byte size again. If the image still exceeds the target, the upload is rejected with a serializer validation error.

## Issues Fixed

- Added a "never bigger than original" safety net.
- Fixed PNG lossless/lossy misclassification by counting colors on the normalized image instead of a thumbnail sample.
- Gave opaque PNGs the same color-count-based lossless path as transparent PNGs, so screenshots, diagrams, and icons are not unconditionally converted to lossy JPEG.
- Added lossless WEBP as the first transparent-PNG fallback before lossy WEBP.
- Added adaptive quality and resize retries for JPEG, WEBP, and AVIF.
- Fixed EXIF orientation loss after compression.
- Added hard decompression-bomb protection.
- Preserved animated GIF/PNG/WEBP images instead of flattening them.
- Fixed WEBP/AVIF mode-safety for palette and CMYK images.
- Fixed quantized PNG target-size handling.
- Switched raster optimization from extension-based routing to detected-format routing.
- Normalized output filenames when uploaded file extensions do not match real image formats.
- Replaced weak SVG string validation with safer XML parsing and SVG safety checks.
- Added SVG dimension validation through `width`/`height` or `viewBox`.

## Tests Added or Updated

Image optimizer tests cover:
- empty uploads
- unsupported extensions
- SVG pass-through
- GIF pass-through
- opaque PNG to JPEG conversion
- transparent PNG preservation
- actual format detection when extension is wrong
- hard pixel-limit rejection
- transparency detection
- low-color opaque PNG preservation as PNG
- low-color PNG quantization
- high-color PNG quantization skip behavior
- transparent PNG fallback to WEBP when quantized output still exceeds the target
- oversized PNG resizing

Validator tests cover:
- valid raster images
- invalid image bytes
- unsupported raster formats
- raster dimension limits
- valid SVG uploads
- SVG dimensions from `viewBox`
- SVG rejection when dimensions are required but missing
- unsafe SVG script rejection
- unsafe SVG event-handler rejection
- invalid SVG root rejection

## Verification

Syntax verification completed:

```bash
./venv/bin/python -m py_compile apps/core/services/image_optimizer.py apps/core/tests/test_image_optimizer.py
./venv/bin/python -m py_compile apps/core/validators.py apps/core/tests/test_validators.py
```

Focused Django tests completed in the project virtual environment:

```bash
./venv/bin/python manage.py test apps.core.tests.test_image_optimizer
./venv/bin/python manage.py test apps.core.tests.test_validators
```

Both focused test suites passed.

## Suggested Demo for Instructor

1. Upload a small already-optimized PNG and show that the original is kept if JPEG would be larger.
2. Upload a wrongly named raster file, such as a PNG named `.jpg`, and show the detected format is used.
3. Upload a transparent PNG graphic and show it remains PNG when it fits the target.
4. Upload a transparent PNG that cannot meet the target losslessly and show WEBP fallback.
5. Upload a GIF or animated image and show it is preserved unchanged.
6. Upload an SVG with `viewBox` and show dimension validation works.
7. Upload an SVG with `<script>` or `onclick` and show it is rejected.
