# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Project Setup
- Initialized Django project with `config/` (settings, urls, wsgi/asgi) and `apps/` package structure (`core`, `sites`, `pages`)
- Configured environment variables via `python-dotenv`, `.env` for DB/secret credentials
- Set up PostgreSQL in Docker (`docker-compose.yml`), Django running locally against it via `localhost`
- Added `.gitignore` for env, venv, and Django artifacts
- Added health check endpoint (`GET /api/health/`) verifying DB connectivity
- Added Swagger/OpenAPI schema generation and documentation support

### Site & Page Models
- Added `Site` model: `user` (owner), `status` (draft/published/suspended), `favicon`, `logo`, `global_css`, with file size/type validators
- Added `Page` model: `site` FK, `title`, `slug` (auto-generated), `status`, `page_type`, `html`/`css` files, unique slug per site constraint
- Added Django admin registration for both models with appropriate readonly fields and filters
- Configured media storage (`MEDIA_URL`, `MEDIA_ROOT`) for uploaded files
- Added comprehensive `ImageValidator` supporting PNG, JPEG, WEBP, GIF, AVIF, and SVG, with size and dimension rules
- Added `Site.thumbnail` field with 100-800px dimension limits and 50KB max size
- Added `Page.hero_image` field with 400-2500px dimension limits and 300KB max size, suitable for page-specific hero banners
- Added role-based image presets for favicon (16-512px, 50KB) and logo (50-1000px, 150KB)

### Image Optimization
- Added `ImageOptimizer` service for upload-time image compression and format handling.
- Added `ImageOptimizationMixin` to auto-compress configured DRF image fields during `create()` and `update()`.
- Refactored image compression logic by replacing `ImageOptimizationMixin` with a dedicated `ImageFieldProcessor` service in `apps/core/utils/image_field_processor.py`; `SiteSerializer`, `SiteImageSerializer`, and `PageSerializer` now invoke it directly from their own `create()`/`update()` methods with no behavior change.

### Site Images API
- Added nested site image endpoints:
  - `GET /api/v1/sites/{site_pk}/images/`
  - `POST /api/v1/sites/{site_pk}/images/`
  - `GET /api/v1/sites/{site_pk}/images/{pk}/`
  - `PUT/PATCH /api/v1/sites/{site_pk}/images/{pk}/`
  - `DELETE /api/v1/sites/{site_pk}/images/{pk}/`
- Added `SiteImageSerializer` and site-scoped image views.

### Authentication
- Added JWT authentication via `djangorestframework-simplejwt` (access/refresh token rotation, blacklist-after-rotation)
- Added `POST /api/auth/register/` with Django's `AUTH_PASSWORD_VALIDATORS` enforced
- Added `POST /api/auth/login/` and `POST /api/auth/refresh/`

### API Design
- Converted Site/Page endpoints from DRF ViewSets to explicit class-based `APIView`s for per-method HTTP visibility
- Nested Page endpoints under Site: `/api/sites/{site_pk}/pages/` and `/api/sites/{site_pk}/pages/{pk}/`
- Added validation: Site name uniqueness (global), Page slug uniqueness (per-site)

### Access Control
- Changed access model: any authenticated user can view/edit any Site or Page (no per-owner restriction)
- Added global Django permission `sites.can_edit_site` (via `Site.Meta.permissions`), assignable per-user through Django admin
- Added `HasSiteUpdatePermission`: read open to all authenticated users; write requires site ownership or the global permission
- Applied permission checks across Site/Page views via explicit `check_object_permissions()` calls
- Changed `Site.favicon` and `Site.logo` to use `ImageValidator` instead of simpler size-only validators

### Redis-Based Site Locking
- Added `SiteLockService` using `django-redis` cache backend (atomic `cache.add` for lock acquisition)
- Lock is site-level only — locking a Site also covers every Page under it (single cache key per site)
- Locking applies only to write operations (POST/PUT/PATCH/DELETE), not to reads
- Consolidated lock control into a single dedicated resource: `GET/PATCH/DELETE /api/sites/{pk}/lock/` (acquire-or-status / heartbeat / release)
- Lock metadata includes `user_id`, `username`, `locked_at`, `last_activity_at`, `ttl_remaining_seconds`
- Deleting a Site force-clears its associated lock key

### Google Docs Blog Importer
- Added service-layer architecture: `GoogleDocsClient`, `ImageHandler`, `HTMLCleaner`, `HTMLSanitizer`, `BlogImporterService`
- Imports blogs from a public Google Doc's tabs (no API/credentials required), one tab per blog
- Base64 inline images decoded and saved to media storage; title extracted from each tab's `<h1>`
- Idempotent via `Page.objects.get_or_create` (site + slug) — re-running always upserts
- Added `import_blogs` management command as a thin entry point

### Site Publish Feature
- Added `Site.header` / `Site.footer` FileFields (reusing existing HTML validators)
- Added `HTMLMinifier` service: repairs malformed HTML and collapses whitespace (separate from the blog-import cleaner/sanitizer)
- Added `HTMLToJSONConverter`: wraps minified HTML + metadata into a JSON dict (not a DOM/AST parser)
- Added `PublishService`: validates readiness, writes JSON artifacts to `media/assets/sites/{id}/`, flips Site/Page status to `published` only after all writes succeed
- Added `POST /api/v1/sites/{id}/publish/` (reuses existing permission + lock enforcement)
- Exposed `header`/`footer` via the Site API (multipart upload), in addition to Django admin

### Site Metadata
- Added `Site.url` (manually entered custom domain/URL)
- Added `Site.created_by` (alongside existing `user`, for naming symmetry with Page and future ownership-transfer support)
- Added nested `SiteSummarySerializer` (`id`, `name`, `status`, `url`) embedded in Page responses

### Testing
- Restructured `tests.py` files into `tests/` packages across `apps/core`, `apps/sites`, `apps/pages`
- Added serializer tests (validation, read-only field protection), view tests (permissions, CRUD), and lock tests (acquire/heartbeat/release/status)
- Added publish endpoint test coverage per acceptance checklist (happy path, validation errors, permission/lock enforcement, whitespace cleaning verification)
- Added site publish test coverage for unauthenticated 401, empty header/footer content rejection, disabled-page exclusion, orphaned page JSON cleanup on republish, failed-republish preserving prior assets, stronger footer/page HTML minify assertions, and exact JSON schema verification for response and artifact files

### Fixed
- Site publish: safe republish — writes now use a temp-then-swap pattern instead of delete-then-save, preventing loss of live assets on partial failure
- Site publish: removed orphaned page JSON files (disabled/deleted/renamed pages) after each publish
- Site publish: DB status update now wrapped in `transaction.atomic()`, applied only after all files are safely written
- Site publish: empty header/footer file content is now rejected (400), not just missing files
- HTMLMinifier: replaced regex-based whitespace collapsing with DOM-level text-node processing, so internal newlines/whitespace in text content are properly collapsed
- HTMLMinifier: content inside `<script>`, `<style>`, `<pre>`, and `<textarea>` is left untouched
- Added dedicated unit tests for HTMLMinifier covering malformed tags, script/pre/textarea preservation, and inline-element spacing
