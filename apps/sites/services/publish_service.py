import json

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import transaction
from django.db.models import Max
from django.utils.text import slugify

from apps.core.exceptions import PublishValidationError
from apps.pages.models import Page
from apps.sites.models import Site, SitePublishVersion
from apps.sites.services.blob_store import BlobStore
from apps.sites.services.html_minifier import HTMLMinifier
from apps.sites.services.html_to_json import HTMLToJSONConverter


class PublishService:
    def __init__(self):
        self.minifier = HTMLMinifier()
        self.converter = HTMLToJSONConverter()
        self.blobs = BlobStore()

    def _read(self, file_field):
        with file_field.open("r") as f:
            return f.read()

    def _validate_readiness(self, site, pages):
        if not site.header or not site.footer:
            raise PublishValidationError(
                "Both header and footer HTML are required to publish."
            )
        if not pages:
            raise PublishValidationError(
                "Site must have at least one enabled page with HTML to publish."
            )
        if not self._read(site.header).strip():
            raise PublishValidationError("Header file is empty.")
        if not self._read(site.footer).strip():
            raise PublishValidationError("Footer file is empty.")

    def _build_json(self, site, pages):
        header_html = self.minifier.minify(self._read(site.header))
        header_json = (
            json.dumps(
                self.converter.convert_header(site, header_html),
                indent=2,
            )
            + "\n"
        )

        footer_html = self.minifier.minify(self._read(site.footer))
        footer_json = (
            json.dumps(
                self.converter.convert_footer(site, footer_html),
                indent=2,
            )
            + "\n"
        )

        page_jsons = {
            page.slug: json.dumps(
                self.converter.convert_page(
                    site, page, self.minifier.minify(self._read(page.html))
                ),
                indent=2,
            )
            + "\n"
            for page in pages
        }
        return header_json, footer_json, page_jsons

    def _snapshot_file(self, file_field):
        if not file_field:
            return None
        with file_field.open("rb") as file:
            content_hash = self.blobs.put(file.read())
        return {"hash": content_hash, "name": file_field.name.rsplit("/", 1)[-1]}

    def _snapshot_assets(self, site, pages):
        assets = {
            "site.global_css": self._snapshot_file(site.global_css),
        }
        for page in pages:
            assets[f"page:{page.slug}:css"] = self._snapshot_file(page.css)
        return assets

    def _restore_file(self, instance, field_name, asset):
        field = getattr(instance, field_name)
        if asset is None:
            if field:
                field.delete(save=False)
            setattr(instance, field_name, None)
            return
        content = self.blobs.read(asset["hash"])
        field.save(asset["name"], ContentFile(content), save=False)

    def _restore_file_reference(self, instance, field_name, path):
        field = getattr(instance, field_name)
        field.name = path or None

    def _replace_published_file(self, path, content):
        """Replace a published JSON file and restore its old bytes on failure."""
        content_bytes = content.encode("utf-8")
        previous_bytes = None

        if default_storage.exists(path):
            with default_storage.open(path, "rb") as file:
                previous_bytes = file.read()
            default_storage.delete(path)

        try:
            default_storage.save(path, ContentFile(content_bytes))
        except Exception:
            if default_storage.exists(path):
                default_storage.delete(path)
            if previous_bytes is not None:
                default_storage.save(path, ContentFile(previous_bytes))
            raise

    def _cleanup_orphan_pages(self, site, expected_slugs):
        pages_dir = f"assets/sites/{slugify(site.name)}/pages/"
        expected_filenames = {f"{slug}.json" for slug in expected_slugs}

        try:
            _, filenames = default_storage.listdir(pages_dir)
        except FileNotFoundError:
            return

        for filename in filenames:
            if filename not in expected_filenames and not filename.endswith(".tmp"):
                default_storage.delete(f"{pages_dir}{filename}")

    def _next_version_number(self, site):
        latest = site.publish_versions.aggregate(Max("version_number"))[
            "version_number__max"
        ]
        return (latest or 0) + 1

    def publish(self, site, user=None):
        pages = list(
            site.pages.filter(enable=True, html__isnull=False).exclude(html="")
        )
        self._validate_readiness(site, pages)

        header_json, footer_json, page_jsons = self._build_json(site, pages)

        header_hash = self.blobs.put(header_json.encode("utf-8"))
        footer_hash = self.blobs.put(footer_json.encode("utf-8"))
        page_hashes = {
            slug: self.blobs.put(content.encode("utf-8"))
            for slug, content in page_jsons.items()
        }
        asset_hashes = self._snapshot_assets(site, pages)

        self._replace_published_file(
            f"assets/sites/{slugify(site.name)}/header.json", header_json
        )
        self._replace_published_file(
            f"assets/sites/{slugify(site.name)}/footer.json", footer_json
        )
        for slug, content in page_jsons.items():
            self._replace_published_file(
                f"assets/sites/{slugify(site.name)}/pages/{slug}.json", content
            )
        self._cleanup_orphan_pages(site, page_jsons.keys())

        written_files = ["header.json", "footer.json"] + [
            f"pages/{slug}.json" for slug in page_jsons
        ]

        with transaction.atomic():
            locked_site = Site.objects.select_for_update().get(pk=site.id)
            existing_version = locked_site.publish_versions.filter(
                header_hash=header_hash,
                footer_hash=footer_hash,
                page_hashes=page_hashes,
                asset_hashes=asset_hashes,
            ).first()
            version = existing_version or SitePublishVersion.objects.create(
                site=locked_site,
                version_number=self._next_version_number(locked_site),
                header_hash=header_hash,
                footer_hash=footer_hash,
                page_hashes=page_hashes,
                asset_hashes=asset_hashes,
                published_by=user,
            )
            locked_site.status = locked_site.Status.PUBLISHED
            locked_site.current_published_version = version
            locked_site.save(update_fields=["status", "current_published_version"])
            Page.objects.filter(pk__in=[p.pk for p in pages]).update(
                status=Page.Status.PUBLISHED
            )

        site.refresh_from_db(fields=["status", "current_published_version"])

        return {
            "message": "Site published successfully.",
            "site": {
                "id": site.id,
                "status": site.status,
                "current_published_version": version.version_number,
            },
            "version": {
                "id": version.id,
                "number": version.version_number,
                "published_at": version.created_at,
                "published_by": version.published_by_id,
            },
            "snapshot": {
                "assets_path": f"assets/sites/{slugify(site.name)}/",
                "files": written_files,
            },
        }

    def has_unpublished_changes(self, site):
        """True if live editable source differs from what's currently published."""
        current = site.current_published_version
        if not current:
            return True

        pages = list(
            site.pages.filter(enable=True, html__isnull=False).exclude(html="")
        )

        header_json, footer_json, page_jsons = self._build_json(site, pages)

        header_hash = self.blobs.put(header_json.encode("utf-8"))
        footer_hash = self.blobs.put(footer_json.encode("utf-8"))
        page_hashes = {
            slug: self.blobs.put(content.encode("utf-8"))
            for slug, content in page_jsons.items()
        }
        asset_hashes = self._snapshot_assets(site, pages)

        return (
            header_hash != current.header_hash
            or footer_hash != current.footer_hash
            or page_hashes != current.page_hashes
            or asset_hashes != current.asset_hashes
        )

    def restore_source(self, site, version, user):
        if version.site_id != site.id:
            raise PublishValidationError(
                "This publish version does not belong to this site."
            )

        # Read the immutable version blobs

        header_data = json.loads(self.blobs.read(version.header_hash).decode("utf-8"))
        footer_data = json.loads(self.blobs.read(version.footer_hash).decode("utf-8"))
        page_data_by_slug = {
            slug: json.loads(self.blobs.read(page_hash).decode("utf-8"))
            for slug, page_hash in version.page_hashes.items()
        }
        asset_hashes = version.asset_hashes or {}

        # Restore Site

        site.name = header_data["site_name"]
        site.header.save(
            "header.html", ContentFile(header_data["html"].encode("utf-8")), save=False
        )
        site.footer.save(
            "footer.html", ContentFile(footer_data["html"].encode("utf-8")), save=False
        )
        self._restore_file(
            site,
            "global_css",
            asset_hashes.get("site.global_css"),
        )
        self._restore_file_reference(site, "favicon", header_data.get("favicon"))
        self._restore_file_reference(site, "logo", header_data.get("logo"))
        self._restore_file_reference(site, "thumbnail", header_data.get("thumbnail"))

        site.updated_by = user

        # Load current pages
        pages_by_slug = {page.slug: page for page in site.pages.all()}

        restored_pages = []

        # Restore pages from the target version
        for slug, data in page_data_by_slug.items():
            page = pages_by_slug.get(slug)

            if page is None:
                page = Page(
                    site=site,
                    slug=slug,
                    created_by=user,
                )

            page.title = data["title"]
            page.meta_description = data["meta_description"]
            page.page_type = data["page_type"]

            page.html.save(
                f"{slug}.html",
                ContentFile(data["html"].encode("utf-8")),
                save=False,
            )
            self._restore_file(
                page,
                "css",
                asset_hashes.get(f"page:{slug}:css"),
            )
            self._restore_file_reference(page, "hero_image", data.get("hero_image"))

            page.enable = True
            page.status = Page.Status.PUBLISHED
            page.updated_by = user

            page.save()

            restored_pages.append(slug)

        # Remove pages that do not exist in the target version so the editable
        # database state matches the rollback snapshot.

        restored_slugs = set(page_data_by_slug)

        pages_to_disable = [
            page
            for slug, page in pages_by_slug.items()
            if slug not in restored_slugs and page.pk
        ]

        removed_pages = [page.slug for page in pages_to_disable]

        if pages_to_disable:
            Page.objects.filter(pk__in=[page.pk for page in pages_to_disable]).delete()

        # Save Site

        site.save(
            update_fields=[
                "name",
                "header",
                "footer",
                "favicon",
                "logo",
                "thumbnail",
                "global_css",
                "updated_by",
            ]
        )

        return {
            "restored_pages": restored_pages,
            "removed_pages": removed_pages,
        }

    def rollback(self, site, version, user=None):
        if version.site_id != site.id:
            raise PublishValidationError(
                "This publish version does not belong to this site."
            )

        from_version = site.current_published_version
        from_version_number = from_version.version_number if from_version else None

        with transaction.atomic():
            restore_result = self.restore_source(site, version, user)
            publish_result = self.publish(site, user=user)

        return {
            "message": "Rollback completed successfully.",
            "from_version": {"number": from_version_number},
            "to_version": {"number": version.version_number},
            "restored": {
                "site": True,
                "header": True,
                "footer": True,
                "pages": restore_result["restored_pages"],
                "assets": True,
            },
            "removed": {"pages": restore_result["removed_pages"]},
        }
