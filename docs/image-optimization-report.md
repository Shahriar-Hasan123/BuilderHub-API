```markdown
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

1. **`ImageValidator`**
   - Validates image type and dimensions before serializer save.
   - Handles raster images with Pillow.
   - Handles SVGs with safe XML parsing through `defusedxml`.

2. **`ImageFieldProcessor`**
   - Runs during serializer `create()` and `update()`.
   - Calls the optimizer for configured image fields.
   - Re-checks the final optimized size against each field's max KB limit.
   - Replaces the upload with a Django `ContentFile` before model save.

3. **`ImageOptimizer`**
   - Compresses raster images.
   - Preserves SVG, GIF, and animated images.
   - Applies adaptive compression for lossy formats.
   - Falls back to the original if optimization would make the file larger.

## Why Lossless vs. Lossy — the Design Rationale

Before describing the flow, it's worth stating the principle the whole optimizer is built around, since "lossless" and "lossy" are easy to treat as a binary choice when they're really a trade-off decided by image content.

**Lossless compression** (PNG, lossless WEBP) works by removing *redundancy* — repeated pixels, flat color regions, predictable patterns — without discarding any actual image data. How much it can shrink a file depends entirely on how much redundancy the image contains:

- **Low-color graphics** (icons, logos, screenshots, diagrams, flat-color illustrations) have a lot of redundancy. Lossless compression alone typically achieves large size reductions here, often close to what lossy compression would achieve — with zero quality loss.
- **Photographs** (gradients, texture, noise, millions of distinct colors) have very little redundancy. Lossless compression on a real photo usually only reduces size by 20–50%. A 5MB camera photo might become 2.5–3.5MB losslessly — it will not reach 150KB, because that size reduction would require discarding real image information, not just redundant data. This is a hard limit rooted in information theory (Shannon entropy), not a limitation of any particular tool or setting.

**This is why the optimizer cannot use lossless compression unconditionally.** The task's own size targets (50KB for icons, 150–300KB for regular/hero images) are only achievable for photo-like images through lossy compression. Applying lossless everywhere would satisfy "lossless" as a word but fail the size requirement for any real photograph — the two goals conflict for that image class.

**The resolution used in this implementation is *lossless-first, lossy-only-as-a-last-resort*:**

1. Try quantized PNG (lossless, if the image genuinely has ≤256 colors).
2. Try full lossless PNG.
3. Try lossless WEBP (often smaller than PNG at zero quality loss).
4. Only if none of the above meet the target size, fall back to lossy compression (JPEG for opaque images, lossy WEBP where alpha must be preserved), lowering quality and then resizing as needed to reach the target.

This means:
- Icons, logos, and other low-color graphics are compressed **losslessly** in the common case — no quality loss.
- Photographs and other high-color images are compressed **losslessly first**, and only drop to lossy compression when the size target cannot otherwise be met — and even then, quality starts high (75) and only decreases as needed.

This mirrors standard practice in production image pipelines (e.g. Squoosh, Cloudinary's auto-format selection): the lossy/lossless decision is driven by the image's actual color complexity, not by its file extension or a blanket policy.

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
        |-- PNG (shared path for opaque and transparent)
        |     |
        |     |-- detect real transparency
        |     |-- normalize to RGBA (transparent) or RGB (opaque)
        |     |-- resize very large PNGs to max 1500px side
        |     |-- count colors on the normalized image
        |     |
        |     |-- <=256 colors -> quantized PNG (lossless)
        |     |     |-- meets target -> return
        |     |
        |     |-- full lossless PNG
        |     |     |-- meets target -> return
        |     |
        |     |-- lossless WEBP
        |     |     |-- meets target -> return
        |     |
        |     |-- still above target -> lossy fallback
        |           |-- has alpha -> adaptive lossy WEBP
        |           |-- opaque    -> adaptive JPEG
        |
        |-- JPEG / WEBP / AVIF -> adaptive lossy compression
        |
        v
Compare best candidate bytes with original bytes
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

If no target size is supplied, the optimizer stops at the first successful lossless result instead of running the lossy ladder — no size pressure means no reason to accept quality loss.

## Key Behaviors

### Never bigger than original
Every compression path produces a candidate, and the smallest candidate seen across all attempted tiers (quantized PNG, lossless PNG, lossless WEBP, lossy) is compared against the original byte length. The optimized result is only used when it is smaller. This prevents the common failure mode where recompressing an already-efficient image makes it larger.

### Actual format detection
Raster routing uses Pillow's decoded format, not only the uploaded filename extension. If a PNG is uploaded as `wrong.jpg`, the optimizer still treats it as PNG and normalizes the output filename extension to match.

### PNG handling
PNG images use a single, shared lossless-first path regardless of transparency:
- Low-color PNGs — transparent or opaque — are quantized losslessly first.
- PNGs are resized to a maximum 1500px side before any lossless attempt.
- Quantized PNGs are also checked against `target_bytes`; they no longer return early while still exceeding the target.
- All PNGs try lossless WEBP before any lossy fallback.
- Opaque PNGs fall back to adaptive JPEG when lossless options can't meet the target, since transparency doesn't need to be preserved — this is usually far smaller than lossy WEBP for photo-like PNG uploads.
- Transparent PNGs fall back to adaptive lossy WEBP (the only lossy format here that preserves alpha).

### Animated image preservation
GIF and animated raster images (including animated PNG/WEBP) are returned unchanged. This avoids silently collapsing an animation into a static first frame.

### EXIF orientation
`ImageOps.exif_transpose()` is applied after load so phone/camera images keep their expected orientation after EXIF metadata is dropped during save.

### Decompression-bomb protection
The optimizer checks `opened.width * opened.height` against `MAX_IMAGE_PIXELS` before loading pixel data, rejecting oversized images safely before expensive memory work.

### WEBP/AVIF mode safety
Palette, CMYK, and other uncommon color modes are normalized to RGB or RGBA before saving to lossy formats, avoiding encoder crashes.

## SVG Validation Flow

SVGs are not raster-optimized. They are validated and then passed through unchanged, since SVG is already a compact, lossless, resolution-independent format — recompressing it isn't meaningful the way it is for raster images.

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
- Fixed PNG lossless/lossy misclassification by counting colors on the normalized image instead of a downsized thumbnail sample.
- Gave opaque PNGs the same color-count-based lossless path as transparent PNGs, so screenshots, diagrams, and icons are not unconditionally converted to lossy JPEG.
- Added lossless WEBP as an intermediate fallback before lossy WEBP/JPEG.
- Added adaptive quality and resize retries for JPEG, WEBP, and AVIF.
- Fixed EXIF orientation loss after compression.
- Added hard decompression-bomb protection.
- Preserved animated GIF/PNG/WEBP images instead of flattening them to a static frame.
- Fixed WEBP/AVIF mode safety for palette and CMYK images.
- Fixed quantized PNG target-size handling (previously returned early without checking the target).
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

1. Upload a small already-optimized PNG and show that the original is kept if re-encoding would make it larger.
2. Upload a wrongly named raster file, such as a PNG named `.jpg`, and show the detected format is used instead of the extension.
3. Upload a low-color transparent PNG graphic and show it stays losslessly compressed PNG when it fits the target.
4. Upload a low-color opaque PNG (e.g. a screenshot) and show it also stays lossless PNG rather than being converted to JPEG.
5. Upload a high-color transparent PNG that cannot meet the target losslessly and show the lossless-WEBP-then-lossy-WEBP fallback.
6. Upload a GIF or animated image and show it is preserved unchanged.
7. Upload an SVG with `viewBox` and show dimension validation works.
8. Upload an SVG with `<script>` or `onclick` and show it is rejected.
9. **Explain the lossless-first design**: show a favicon/icon staying lossless, and a large photo needing the lossy fallback to meet its 150–300KB target — demonstrating the size-vs-fidelity trade-off is deliberate and content-driven, not accidental.
```