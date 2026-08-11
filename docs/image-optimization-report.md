# Image Optimization Report — 2026-08-11

## Task Overview

This feature improves the image upload pipeline by validating images safely,
optimizing raster images at upload time, preserving formats that should not be
recompressed by default, and enforcing field-specific size limits before files
are saved.

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

2. **`ImageOptimizer`**
   - Performs best-effort optimization.
   - Preserves SVG, GIF, and animated images.
   - Keeps the original file if the optimized candidate is not smaller.
   - Uses conservative defaults: no lossy compression and no resizing unless a
     caller explicitly enables them.

3. **`ImageFieldProcessor`**
   - Runs during serializer `create()` and `update()`.
   - Calls the optimizer for configured image fields.
   - Explicitly enables lossy compression and resizing because serializer image
     fields have hard KB targets.
   - Re-checks the final optimized size and rejects the upload if it still
     exceeds the field limit.
   - Replaces the upload with a Django `ContentFile` before model save.

## Design Rationale

Lossless and lossy compression solve different problems.

**Lossless optimization** removes redundant storage without intentionally
discarding image information. It works very well for low-color graphics such as
icons, logos, screenshots, diagrams, and flat illustrations.

**Lossy compression** discards detail to hit much smaller file sizes. It is often
necessary for photo-like images when product requirements demand strict targets
such as 50 KB, 150 KB, or 300 KB.

The current design makes this policy explicit:

- `ImageOptimizer.compress()` defaults to conservative, non-resizing,
  non-lossy optimization.
- Destructive operations are opt-in through `allow_lossy=True` and
  `allow_resize=True`.
- The upload pipeline opts in because it must enforce strict field size limits.
- The optimizer is best-effort; the caller is responsible for re-checking hard
  size limits.

This avoids accidentally degrading images when the optimizer is reused outside
the upload path, while still allowing the serializer workflow to meet product
size limits when possible.

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
ImageOptimizer.compress(
    uploaded_file,
    target_kb=max_kb,
    allow_lossy=True,
    allow_resize=True,
)
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
ImageOptimizer.compress(file, target_kb=None, allow_lossy=False, allow_resize=False)
        |
        v
Check empty file and supported extension
        |
        v
Read original bytes
        |
        |-- original size already <= target -> return original bytes unchanged
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
Load image, capture ICC profile, apply EXIF transpose
        |
        |-- GIF or animated image -> return original bytes unchanged
        |
        v
If source is already lossy (JPEG):
        |
        |-- allow_lossy=False -> keep original
        |
        |-- allow_lossy=True  -> use adaptive JPEG/WebP fallback
        |
        v
For non-lossy raster sources such as PNG, WEBP, or AVIF:
        |
        |-- detect real transparency
        |-- normalize to RGBA when alpha exists, otherwise RGB
        |
        |-- <=256 decoded colors -> lossless palette PNG candidate when quantization is truly lossless
        |
        |-- same-format lossless candidate for WEBP/AVIF when available
        |
        |-- full lossless PNG candidate
        |
        |-- lossless WebP candidate
        |
        |-- still above target and allow_lossy=True:
        |       |-- has alpha -> adaptive lossy WebP
        |       |-- opaque    -> adaptive JPEG
        |
        v
Compare candidate bytes with original bytes
        |
        |-- candidate smaller -> return candidate
        |
        |-- candidate missing/same/larger -> return original
```

## Adaptive Lossy Flow

Lossy compression only runs when `allow_lossy=True`.

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
if allow_resize=True and target still missed:
   |
   |-- downscale and retry quality ladder
   |-- repeat up to MAX_RESIZE_RETRIES
```

If `allow_resize=False`, dimensions are not changed. If `allow_lossy=False`,
the quality ladder is skipped completely.

## Key Behaviors

### Conservative Defaults

`ImageOptimizer.compress()` is safe to reuse in contexts where image quality
should not be degraded by default:

- JPEG uploads are not quantized and are not recompressed by default.
- Image dimensions are not changed by default.
- Lossy quality reduction is not used by default.
- Original bytes are kept if optimization does not produce a smaller result.

### Explicit Upload Policy

`ImageFieldProcessor` passes `allow_lossy=True` and `allow_resize=True` because
site images, content images, and hero images have strict KB limits. After
optimization, it checks the final byte size again. If the result still exceeds
the configured limit, the serializer rejects the upload.

### Never Bigger Than Original

The optimizer compares the candidate output against the original upload. The
candidate is only used when it is smaller. This prevents recompression from
making already-efficient files larger.

### Target-Size Fast Path

If the original upload already meets the requested `target_kb`, the optimizer
returns the original bytes unchanged and skips heavy re-encoding.

### Actual Format Detection

Raster routing uses Pillow's decoded format, not only the uploaded filename
extension. A PNG uploaded as `wrong.jpg` is still treated as PNG internally.

### Low-Color Palette Optimization

For non-JPEG raster sources with 256 or fewer decoded colors, the optimizer
attempts a truly lossless palette PNG candidate. This is intended for genuine
low-color graphics such as icons, logos, and simple illustrations.

### Same-Format Lossless Candidates

For WEBP and AVIF sources, the optimizer now attempts same-format lossless
output when practical before falling back to other lossless container formats.

### Lossless PNG and WebP Candidates

For these raster sources, the optimizer tries same-format lossless output for
WEBP/AVIF when available, then full lossless PNG and lossless WebP before any
lossy fallback is considered.

### Animated Image Preservation

GIF and animated raster images, including animated PNG/WebP, are returned
unchanged. This avoids silently collapsing animation to a static frame.

### EXIF Orientation

`ImageOps.exif_transpose()` is applied after load so phone/camera images keep
their expected orientation after optimization.

### ICC Profile Handling

The optimizer captures the source ICC profile and passes it to supported output
save paths where practical, reducing the risk of visible color shifts.

### Decompression-Bomb Protection

The optimizer checks `opened.width * opened.height` against `MAX_IMAGE_PIXELS`
before processing pixel data and raises `UnsupportedImageFormatError` for
oversized images.

### SVG Validation Contract

SVG files are passed through unchanged by the optimizer based on extension. SVG
safety is handled upstream by `ImageValidator`, which parses with `defusedxml`
and rejects unsafe tags, event handlers, and unsafe link values.

## SVG Validation Flow

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

## Field Integration

Configured serializer fields provide their target sizes:

```text
SiteSerializer:
  favicon    -> 50 KB
  logo       -> 50 KB
  thumbnail  -> 50 KB

SiteImageSerializer:
  image      -> 150 KB

PageSerializer:
  hero_image -> 300 KB
```

The field processor calls:

```python
ImageOptimizer().compress(
    uploaded_file,
    target_kb=max_kb,
    allow_lossy=True,
    allow_resize=True,
)
```

Then it rejects the upload if `len(content_bytes) > max_kb * 1024`.

## Issues Fixed

- Added a "never bigger than original" safety net.
- Kept the original file when the optimized candidate is not smaller.
- Made lossy compression explicit through `allow_lossy`.
- Made resizing explicit through `allow_resize`.
- Changed optimizer defaults so lossless-first optimization is the default path,
  and only explicit lossy fallback is used when `allow_lossy=True`.
- Changed optimizer defaults so JPEG uploads are not recompressed by default,
  while AVIF is treated like other raster formats because it can be lossless.
- Removed default PNG resizing before lossless attempts.
- Added a best-effort contract: `compress()` can optimize toward a target, but
  callers must enforce hard limits.
- Preserved animated GIF/PNG/WEBP images instead of flattening them to a static
  frame.
- Added EXIF orientation correction.
- Added ICC profile pass-through where practical.
- Added hard decompression-bomb protection.
- Added a target-size fast path that returns the original upload unchanged when
  the original byte size already satisfies the requested `target_kb`.
- Switched raster optimization from extension-based routing to detected-format
  routing.
- Replaced weak SVG string validation with safer XML parsing and SVG safety
  checks in `ImageValidator`.
- Added SVG dimension validation through `width`/`height` or `viewBox`.

## Tests Added or Updated

Image optimizer tests cover:

- empty uploads
- unsupported extensions
- SVG pass-through
- GIF pass-through
- opaque PNG to JPEG conversion only when lossy is explicitly allowed
- transparent PNG not being converted to JPEG
- JPEG not being recompressed by default
- actual format detection when extension is wrong
- hard pixel-limit rejection
- transparency detection
- low-color opaque PNG preservation as PNG
- low-color palette optimization
- high-color quantization skip behavior
- lossy fallback only when allowed
- default path does not resize
- lossy resize is opt-in

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

Commands run after the optimizer policy update:

```bash
./venv/bin/python manage.py test apps.core.tests.test_image_optimizer
./venv/bin/ruff check apps/core/services/image_optimizer.py apps/core/utils/image_field_processor.py apps/core/tests/test_image_optimizer.py
./venv/bin/python -m py_compile apps/core/services/image_optimizer.py apps/core/utils/image_field_processor.py apps/core/tests/test_image_optimizer.py
```

All three checks passed.

## Image Optimization — Testing Instructions

All image fields are uploaded via `multipart/form-data`, not raw JSON —
Postman: Body → form-data, set the field's type to **File**.

## 1. Site images — favicon / logo / thumbnail (target: 50 KB each)

**Endpoint:** `PATCH /api/v1/sites/{site_id}/`

**Input (Postman form-data):**
| Key | Type | Value |
|---|---|---|
| favicon | File | (pick an image, e.g. a 2MB PNG icon) |

Test separately for `logo` and `thumbnail` the same way (one field at a time,
or all three together in one request).

**Expected output (200 OK):**
```json
{
  "id": 20,
  "name": "w3-school",
  "url": "https://example.com",
  "favicon": "/media/sites/20/favicon_ab12cd34.png",
  "logo": "/media/sites/20/logo_ef56gh78.png",
  "thumbnail": "/media/sites/20/thumbnail_ij90kl12.jpg",
  "status": "draft",
  "user": 1,
  "created_by": 1,
  "updated_by": 1
}
```
**What to verify:**
- Response 200 (not 400) — means optimizer got the file under 50KB
- Download the returned `favicon` URL and check its actual file size ≤ 50KB
- Compare against the original upload size (should be meaningfully smaller, or unchanged if the original was already small — per the "never bigger than original" rule)

**Failure case (400) — upload something that can't possibly reach 50KB even compressed** (e.g. a large, highly detailed photo as favicon):
```json
{
  "favicon": [
    "Even after adaptive compression, this image exceeds 50 KB (got 87.3 KB)."
  ]
}
```

---

## 2. SiteImage — regular gallery image (target: 150 KB)

**Endpoint:** `POST /api/v1/sites/{site_id}/images/`

**Input (Postman form-data):**
| Key | Type | Value |
|---|---|---|
| image | File | (pick a photo, e.g. a 3MB JPEG) |
| alt_text | Text | "Team photo" |
| page | Text | (optional, a page ID under this site) |

**Expected output (201 Created):**
```json
{
  "id": 7,
  "site": 20,
  "page": null,
  "file_name": "image_mn34op56.jpg",
  "image": "/media/sites/20/images/image_mn34op56.jpg",
  "alt_text": "Team photo",
  "file_size": "134.5 KB",
  "width": 1920,
  "height": 1080,
  "created_by": 1,
  "updated_by": 1
}
```
**What to verify:**
- `file_size` (KB) ≤ 150 KB
- `width`/`height` reflect any resize that happened (should be ≤1500px on the longer side if resize was needed)

---

## 3. Page — hero_image (target: 300 KB)

**Endpoint:** `PATCH /api/v1/sites/{site_id}/pages/{page_id}/`

**Input (Postman form-data):**
| Key | Type | Value |
|---|---|---|
| hero_image | File | (pick a large banner photo, e.g. 5MB) |

**Expected output (200 OK):**
```json
{
  "id": 3,
  "site": {
    "id": 20,
    "name": "w3-school",
    "status": "draft",
    "url": "https://example.com"
  },
  "slug": "home-page",
  "title": "Home",
  "status": "draft",
  "page_type": "page",
  "hero_image": "/media/pages/3/hero_qr78st90.jpg",
  "meta_description": "Welcome to our site",
  "canonical_url": "",
  "enable": true,
  "created_by": 1,
  "updated_by": 1
}
```
**What to verify:**
- Download `hero_image`, confirm ≤ 300KB
- If original was a low-color/graphic-style banner, confirm it stayed `.png`/`.webp` (lossless) rather than becoming `.jpg` — proof the lossless-first path is working

---

## Test matrix (run each of these once per field)

| Case | Image type | Expected result |
|---|---|---|
| Small, already tiny (e.g. 10KB icon) | any | Returned unchanged (original kept, not re-encoded larger) |
| Large low-color PNG (screenshot/logo) | PNG | Stays PNG or becomes lossless WEBP — no visible quality loss |
| Large high-color photo | JPEG/PNG | Becomes lossy JPEG/WEBP, quality adaptively reduced until under target |
| Transparent PNG, low-color (icon with alpha) | PNG | Stays lossless PNG |
| Transparent PNG, high-color (photo with alpha) | PNG | Lossless WEBP first, lossy WEBP fallback if still too big |
| Animated GIF/WEBP | GIF/WEBP | Returned unchanged (not flattened to static) |
| SVG | SVG | Passed through unchanged, only validated for safety |
| Rotated phone photo (has EXIF orientation) | JPEG | Comes out right-side-up after compression |

## Suggested Demo for Instructor

1. Upload a small already-optimized PNG and show that the original is kept if
   re-encoding would make it larger.
2. Upload a JPEG with no explicit lossy option and show that it is not
   recompressed by default.
3. Upload a wrongly named raster file, such as a PNG named `.jpg`, and show the
   detected format is used internally.
4. Upload a low-color graphic and show the palette/lossless PNG path.
5. Upload a photo-like PNG through the serializer upload path and show that
   lossy compression is explicitly enabled there to meet the KB target.
6. Upload a GIF or animated image and show it is preserved unchanged.
7. Upload an SVG with `viewBox` and show dimension validation works.
8. Upload an SVG with `<script>` or `onclick` and show it is rejected.
